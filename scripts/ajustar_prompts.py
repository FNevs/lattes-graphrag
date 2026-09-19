"""Gera prompts de indexacao adaptados ao dominio Lattes, com tipos de entidade fixos.

Replica o fluxo de ``graphrag prompt-tune`` (graphrag 3.1.0), com uma diferenca:
a linha de comando so oferece tipos inventados pelo LLM
(``--discover-entity-types``) ou nenhum tipo (prompt "untyped"). Nenhum dos dois
e reproduzivel nem controlavel, entao este script chama os mesmos geradores
internos do GraphRAG passando uma lista de tipos definida aqui.

Tres desvios deliberados em relacao ao prompt-tune da 3.1.0, todos registrados
em ``procedencia.json``:

1. os exemplos de extracao sao gerados por ``gerar_exemplos`` (o gerador
   original tem um bug que pareia cada exemplo com o texto errado);
2. o prompt de resumo perde a frase ``FRASE_ENRIQUECER``, que pede para
   enriquecer a descricao com um texto que o modelo nao recebe;
3. ``restaurar_limites`` devolve aos prompts de resumo e de relatorio o limite
   de tamanho que os templates do prompt-tune omitem.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.metadata
import json
import logging
from pathlib import Path

import numpy as np
from graphrag.config.load_config import load_config
from graphrag.prompt_tune.defaults import MAX_TOKEN_COUNT, PROMPT_TUNING_MODEL_ID
from graphrag.prompt_tune.generator.community_report_rating import (
    generate_community_report_rating,
)
from graphrag.prompt_tune.generator.community_report_summarization import (
    COMMUNITY_SUMMARIZATION_FILENAME,
    create_community_summarization_prompt,
)
from graphrag.prompt_tune.generator.community_reporter_role import (
    generate_community_reporter_role,
)
from graphrag.prompt_tune.generator.entity_relationship import MAX_EXAMPLES
from graphrag.prompt_tune.generator.entity_summarization_prompt import (
    ENTITY_SUMMARIZATION_FILENAME,
    create_entity_summarization_prompt,
)
from graphrag.prompt_tune.generator.extract_graph_prompt import (
    EXTRACT_GRAPH_FILENAME,
    create_extract_graph_prompt,
)
from graphrag.prompt_tune.generator.persona import generate_persona
from graphrag.prompt_tune.loader.input import load_docs_in_chunks
from graphrag.prompt_tune.prompt.entity_relationship import (
    ENTITY_RELATIONSHIPS_GENERATION_PROMPT,
)
from graphrag.prompt_tune.types import DocSelectionType
from graphrag.tokenizer.get_tokenizer import get_tokenizer
from graphrag_llm.completion import create_completion
from graphrag_llm.utils import CompletionMessagesBuilder

LOGGER = logging.getLogger(__name__)

# Tipos derivados da auditoria do grafo V1-NFC: das 490 entidades EVENT, so
# ~17% eram eventos; o resto eram publicacoes, areas de conhecimento, sistemas,
# cursos e projetos. Os tipos acompanham as secoes do XML Lattes (producao
# bibliografica, producao tecnica, projetos, areas de atuacao, formacao).
ENTITY_TYPES_LATTES = [
    "person",
    "organization",
    "geo",
    "event",
    "publication",
    "software",
    "project",
    "knowledge_area",
    "course",
]

# Frase do template de resumo do prompt-tune (entity_summarization.py). Nessa
# etapa o modelo so recebe a lista de descricoes -- nao ha "texto proximo" --,
# entao a instrucao so convida a acrescentar informacao sem fonte. O prompt
# padrao do GraphRAG nao tem essa frase.
FRASE_ENRIQUECER = (
    "Enrich it as much as you can with relevant information from the nearby text, "
    "this is very important."
)

# Os templates do prompt-tune da 3.1.0 nao tem o limite de tamanho que os prompts
# padrao tem; sem ele, summarize_descriptions.max_length e
# community_reports.max_length do settings.yaml deixam de ter efeito.
LIMITE_RESUMO = "Limit the final description length to {max_length} words.\n"
LIMITE_RELATORIO = "Limit the total report length to {max_report_length} words.\n"
ANCORA_RESUMO = "include the entity names so we have the full context.\n"
ANCORA_RELATORIO = "Do not include information where the supporting evidence for it is not provided.\n"
FIM_RELATORIO = "{input_text}\nOutput:"

DOMINIO_PADRAO = (
    "curriculos academicos da Plataforma Lattes (CNPq) de pesquisadores "
    "brasileiros: formacao, producao bibliografica e tecnica, projetos de "
    "pesquisa, orientacoes, eventos, areas de atuacao e vinculos institucionais"
)


def configurar_logging(nivel: str = "INFO") -> None:
    """Configura o logger padrao do script.

    Parameters
    ----------
    nivel : str, default="INFO"
        Nivel de log desejado (DEBUG, INFO, WARNING, ERROR).

    Returns
    -------
    None
        Nao retorna valor.
    """
    logging.basicConfig(
        level=getattr(logging, nivel.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


async def gerar_exemplos(
    llm,
    persona: str,
    docs: list[str],
    idioma: str,
) -> list[str]:
    """Gera os exemplos de extracao, um por chunk, cada um em conversa propria.

    Substitui ``generate_entity_relationship_examples`` do graphrag 3.1.0, que
    reusa UM CompletionMessagesBuilder para todas as chamadas. Como ``build()``
    devolve a mesma lista (nao uma copia) e as tarefas sao montadas antes de
    rodar, as 5 chamadas recebem os 5 chunks empilhados e o modelo responde
    sempre ao ultimo: cada exemplo sai pareado com o texto errado.

    Parameters
    ----------
    llm : LLMCompletion
        Modelo de completion do GraphRAG.
    persona : str
        Persona usada como mensagem de sistema.
    docs : list[str]
        Chunks de exemplo.
    idioma : str
        Idioma das descricoes geradas.

    Returns
    -------
    list[str]
        Uma saida por chunk, na mesma ordem de ``docs`` (no maximo MAX_EXAMPLES).
    """
    tipos = ", ".join(ENTITY_TYPES_LATTES)
    tarefas = []
    for doc in docs[:MAX_EXAMPLES]:
        mensagens = (
            CompletionMessagesBuilder()
            .add_system_message(persona)
            .add_user_message(
                ENTITY_RELATIONSHIPS_GENERATION_PROMPT.format(
                    entity_types=tipos, input_text=doc, language=idioma
                )
            )
            .build()
        )
        tarefas.append(llm.completion_async(messages=mensagens, response_format_json_object=False))
    respostas = await asyncio.gather(*tarefas)
    return [r.content for r in respostas]


def restaurar_limites(prompt_resumo: str, prompt_relatorio: str) -> tuple[str, str]:
    """Reinsere nos prompts gerados os limites de tamanho dos prompts padrao.

    Parameters
    ----------
    prompt_resumo : str
        Prompt de resumo de descricoes gerado pelo prompt-tune.
    prompt_relatorio : str
        Prompt de relatorio de comunidade gerado pelo prompt-tune.

    Returns
    -------
    tuple[str, str]
        Os dois prompts com os marcadores ``{max_length}`` e
        ``{max_report_length}``, nas mesmas posicoes dos prompts padrao.

    Raises
    ------
    ValueError
        Quando um template mudou e as ancoras nao foram encontradas.
    """

    if "{max_length}" not in prompt_resumo:
        if prompt_resumo.count(ANCORA_RESUMO) != 1:
            raise ValueError("Template de resumo mudou; revise ANCORA_RESUMO.")
        prompt_resumo = prompt_resumo.replace(ANCORA_RESUMO, ANCORA_RESUMO + LIMITE_RESUMO)
    if "{max_report_length}" not in prompt_relatorio:
        if prompt_relatorio.count(ANCORA_RELATORIO) != 1 or not prompt_relatorio.endswith(
            FIM_RELATORIO
        ):
            raise ValueError("Template de relatorio mudou; revise ANCORA_RELATORIO.")
        prompt_relatorio = prompt_relatorio.replace(
            ANCORA_RELATORIO, ANCORA_RELATORIO + "\n" + LIMITE_RELATORIO
        )
        prompt_relatorio = prompt_relatorio.removesuffix(FIM_RELATORIO) + (
            "{input_text}\n\n" + LIMITE_RELATORIO + "\nOutput:"
        )
    return prompt_resumo, prompt_relatorio


async def gerar_prompts(
    root: Path,
    dominio: str,
    idioma: str,
    limite: int,
    tamanho_chunk: int,
    semente: int,
) -> tuple[dict[str, str], dict[str, object]]:
    """Gera os tres prompts de indexacao com os tipos de ENTITY_TYPES_LATTES.

    Parameters
    ----------
    root : Path
        Raiz do projeto GraphRAG (onde fica o settings.yaml).
    dominio : str
        Descricao do dominio usada para gerar a persona do LLM.
    idioma : str
        Idioma dos prompts e das saidas (ex.: "Portuguese").
    limite : int
        Quantidade de chunks sorteados como amostra.
    tamanho_chunk : int
        Tamanho, em tokens, dos chunks de exemplo.
    semente : int
        Semente do sorteio dos chunks, para a amostra ser reproduzivel.

    Returns
    -------
    tuple[dict[str, str], dict[str, object]]
        Prompts por nome de arquivo e metadados de procedencia.
    """
    config = load_config(root_dir=root)
    # So afeta a amostragem de exemplos; a indexacao usa o chunking do settings.yaml.
    config.chunking.size = tamanho_chunk
    config.chunking.overlap = 0

    # load_docs_in_chunks sorteia com DataFrame.sample sem random_state.
    np.random.seed(semente)
    docs = await load_docs_in_chunks(
        config=config,
        limit=limite,
        select_method=DocSelectionType.RANDOM,
        logger=LOGGER,
        n_subset_max=300,
        k=15,
    )
    LOGGER.info("Chunks de exemplo sorteados: %s", len(docs))

    modelo = config.get_completion_model_config(PROMPT_TUNING_MODEL_ID)
    llm = create_completion(modelo)

    persona = await generate_persona(llm, dominio)
    avaliacao = await generate_community_report_rating(
        llm, domain=dominio, persona=persona, docs=docs
    )
    exemplos = await gerar_exemplos(llm, persona=persona, docs=docs, idioma=idioma)
    prompt_extracao = create_extract_graph_prompt(
        entity_types=ENTITY_TYPES_LATTES,
        docs=docs,
        examples=exemplos,
        language=idioma,
        json_mode=False,
        tokenizer=get_tokenizer(model_config=modelo),
        max_token_count=MAX_TOKEN_COUNT,
        min_examples_required=2,
    )
    prompt_resumo = create_entity_summarization_prompt(persona=persona, language=idioma)
    if FRASE_ENRIQUECER not in prompt_resumo:
        raise ValueError("Template de resumo mudou; revise FRASE_ENRIQUECER antes de continuar.")
    prompt_resumo = prompt_resumo.replace(FRASE_ENRIQUECER, "").replace("\n\n\n", "\n\n")
    papel = await generate_community_reporter_role(
        llm, domain=dominio, persona=persona, docs=docs
    )
    prompt_relatorio = create_community_summarization_prompt(
        persona=persona,
        role=papel,
        report_rating_description=avaliacao,
        language=idioma,
    )
    prompt_resumo, prompt_relatorio = restaurar_limites(prompt_resumo, prompt_relatorio)

    prompts = {
        EXTRACT_GRAPH_FILENAME: prompt_extracao,
        ENTITY_SUMMARIZATION_FILENAME: prompt_resumo,
        COMMUNITY_SUMMARIZATION_FILENAME: prompt_relatorio,
    }
    procedencia = {
        "graphrag": importlib.metadata.version("graphrag"),
        "modelo": modelo.model,
        "dominio": dominio,
        "idioma": idioma,
        "entity_types": ENTITY_TYPES_LATTES,
        "selecao": "random",
        "limite": limite,
        "tamanho_chunk_exemplos": tamanho_chunk,
        "semente": semente,
        "chunks_sorteados": len(docs),
        "exemplos_gerados": len(exemplos),
        "persona": persona,
        "papel_relator": papel,
        "desvios_do_prompt_tune": [
            "exemplos gerados com uma conversa por chunk (bug do builder compartilhado na 3.1.0)",
            "removida do prompt de resumo a frase: " + FRASE_ENRIQUECER,
            "reinseridos os limites {max_length} e {max_report_length} dos prompts padrao",
        ],
    }
    return prompts, procedencia


def criar_parser_argumentos() -> argparse.ArgumentParser:
    """Cria parser de argumentos para execucao via linha de comando.

    Returns
    -------
    argparse.ArgumentParser
        Parser configurado para a geracao dos prompts.
    """
    parser = argparse.ArgumentParser(
        description="Gera prompts de indexacao do GraphRAG adaptados ao Lattes.",
    )
    parser.add_argument("--root", type=Path, default=Path("."), help="Raiz do projeto.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("prompts/lattes"),
        help="Destino dos prompts (default: prompts/lattes). Nao use prompts/, que tem os originais.",
    )
    parser.add_argument("--domain", type=str, default=DOMINIO_PADRAO, help="Dominio dos documentos.")
    parser.add_argument("--language", type=str, default="Portuguese", help="Idioma de saida.")
    parser.add_argument("--limit", type=int, default=15, help="Chunks sorteados (default: 15).")
    parser.add_argument("--chunk-size", type=int, default=400, help="Tokens por chunk de exemplo.")
    parser.add_argument("--seed", type=int, default=42, help="Semente do sorteio (default: 42).")
    parser.add_argument("--log-level", type=str, default="INFO", help="Nivel de log.")
    return parser


def main() -> int:
    """Gera e grava os prompts, com um arquivo de procedencia ao lado.

    Returns
    -------
    int
        Codigo de status da execucao (0 para sucesso).

    Raises
    ------
    FileExistsError
        Quando o diretorio de saida ja tem prompts (evita sobrescrever sem querer).
    """
    args = criar_parser_argumentos().parse_args()
    configurar_logging(nivel=args.log_level)

    destino = args.output_dir
    if destino.exists() and any(destino.glob("*.txt")):
        raise FileExistsError(f"{destino} ja contem prompts; apague ou escolha outro --output-dir.")

    prompts, procedencia = asyncio.run(
        gerar_prompts(
            root=args.root,
            dominio=args.domain,
            idioma=args.language,
            limite=args.limit,
            tamanho_chunk=args.chunk_size,
            semente=args.seed,
        )
    )

    destino.mkdir(parents=True, exist_ok=True)
    for nome, texto in prompts.items():
        (destino / nome).write_text(texto, encoding="utf-8")
        LOGGER.info("Prompt gravado: %s", destino / nome)
    (destino / "procedencia.json").write_text(
        json.dumps(procedencia, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
