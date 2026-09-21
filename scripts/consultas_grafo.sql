-- Consultas ao grafo do GraphRAG direto nos .parquet, sem servidor e sem custo.
--
-- No DBeaver Community: nova conexao DuckDB, banco ":memory:", abrir este arquivo.
-- No terminal:  .venv\Scripts\python.exe scripts\explorar_grafo.py runs\v1-tuned\output
--
-- Para trocar de versao, mude a pasta nas cinco linhas do bloco abaixo
-- (runs/v1-tuned/output, runs/v1-nfc/output, runs/v1-base-nfkc/output, runs/v0-tcc1/output).

CREATE OR REPLACE VIEW entidades   AS SELECT * FROM 'runs/v1-tuned/output/entities.parquet';
CREATE OR REPLACE VIEW relacoes    AS SELECT * FROM 'runs/v1-tuned/output/relationships.parquet';
CREATE OR REPLACE VIEW comunidades AS SELECT * FROM 'runs/v1-tuned/output/communities.parquet';
CREATE OR REPLACE VIEW relatorios  AS SELECT * FROM 'runs/v1-tuned/output/community_reports.parquet';
CREATE OR REPLACE VIEW trechos     AS SELECT * FROM 'runs/v1-tuned/output/text_units.parquet';

-- 1. Quantas entidades de cada tipo
SELECT type AS tipo, count(*) AS qtd
FROM entidades GROUP BY 1 ORDER BY 2 DESC;

-- 2. Tamanho do grafo (entidades, relacoes, comunidades, trechos)
SELECT (SELECT count(*) FROM entidades)   AS entidades,
       (SELECT count(*) FROM relacoes)    AS relacoes,
       (SELECT count(*) FROM comunidades) AS comunidades,
       (SELECT count(*) FROM trechos)     AS trechos;

-- 3. As 20 entidades mais conectadas (grau)
SELECT title AS entidade, type AS tipo, degree AS grau, frequency AS mencoes
FROM entidades ORDER BY degree DESC LIMIT 20;

-- 4. Procurar uma entidade pelo nome (troque o texto)
SELECT title, type, degree, description
FROM entidades WHERE title ILIKE '%jorge%' ORDER BY degree DESC;

-- 5. Vizinhos de uma pessoa: a que ela esta ligada, por tipo
--    (troque o nome; e assim que se ve "o que o grafo sabe" sobre alguem)
WITH alvo AS (SELECT 'EDUARDO MANUEL DE FREITAS JORGE' AS nome),
vizinhos AS (
  SELECT target AS vizinho, description AS relacao, weight FROM relacoes, alvo WHERE source = alvo.nome
  UNION ALL
  SELECT source AS vizinho, description AS relacao, weight FROM relacoes, alvo WHERE target = alvo.nome)
SELECT e.type AS tipo, v.vizinho, v.relacao, v.weight AS forca
FROM vizinhos v LEFT JOIN entidades e ON e.title = v.vizinho
ORDER BY tipo, forca DESC;

-- 6. Coautoria por caminho de dois passos: pessoas que dividem a mesma publicacao.
--    O prompt curado nao cria aresta pessoa-pessoa; a colaboracao aparece assim.
WITH autoria AS (
  SELECT p.title AS pessoa, o.title AS producao
  FROM relacoes r
  JOIN entidades p ON p.title = r.source AND p.type = 'PERSON'
  JOIN entidades o ON o.title = r.target AND o.type IN ('PUBLICATION', 'SOFTWARE')
  UNION
  SELECT p.title, o.title
  FROM relacoes r
  JOIN entidades p ON p.title = r.target AND p.type = 'PERSON'
  JOIN entidades o ON o.title = r.source AND o.type IN ('PUBLICATION', 'SOFTWARE'))
SELECT a.pessoa AS pessoa_1, b.pessoa AS pessoa_2, count(*) AS producoes_em_comum,
       string_agg(a.producao, ' | ' ORDER BY a.producao) AS exemplos
FROM autoria a JOIN autoria b ON a.producao = b.producao AND a.pessoa < b.pessoa
GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 20;

-- 7. Producao por tipo de registro: quantas publicacoes, softwares e projetos
SELECT type AS tipo, count(*) AS qtd, avg(degree) AS grau_medio
FROM entidades WHERE type IN ('PUBLICATION', 'SOFTWARE', 'PROJECT', 'COURSE') GROUP BY 1;

-- 8. Entidades isoladas (nao entram no grafo do graphml)
SELECT type AS tipo, count(*) AS isoladas
FROM entidades WHERE degree = 0 GROUP BY 1 ORDER BY 2 DESC;

-- 9. Relacoes com linguagem especulativa (controle de qualidade da extracao)
SELECT source, target, description
FROM relacoes
WHERE lower(description) SIMILAR TO '%(provav|possivel|sugere|likely|probabl)%';

-- 10. Comunidades maiores e o titulo do relatorio de cada uma
SELECT c.community AS comunidade, c.level AS nivel, c.size AS tamanho, r.title AS relatorio, r.rank AS nota
FROM comunidades c LEFT JOIN relatorios r ON r.community = c.community AND r.level = c.level
ORDER BY c.size DESC LIMIT 15;

-- 11. Tipos fora da lista de entity_types (defeito de extracao)
SELECT title, type FROM entidades
WHERE type NOT IN ('PERSON','ORGANIZATION','GEO','EVENT','PUBLICATION','SOFTWARE','PROJECT','KNOWLEDGE_AREA','COURSE');

-- 12. Possiveis duplicatas: nomes de pessoa que comecam igual
SELECT a.title, b.title, a.degree, b.degree
FROM entidades a JOIN entidades b
  ON a.type = 'PERSON' AND b.type = 'PERSON' AND a.title < b.title
 AND left(a.title, 10) = left(b.title, 10)
ORDER BY a.title;

-- 13. Em que trecho do curriculo uma entidade foi encontrada (rastreabilidade)
SELECT e.title, t.n_tokens, left(t.text, 300) AS inicio_do_trecho
FROM entidades e, unnest(e.text_unit_ids) AS u(uid)
JOIN trechos t ON t.id = u.uid
WHERE e.title = 'EDUARDO MANUEL DE FREITAS JORGE' LIMIT 5;
