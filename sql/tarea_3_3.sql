-- Reto 3.3 — Atribución determinística de votos de Senado
-- A_ij = (votos_CA_candidato_ij / votos_CA_partido_ij) * votos_SE_partido_ij
-- La fórmula se aplica por municipio y luego se consolida para los 4 municipios.
-- Homologaciones especiales conocidas: Verde 5→57 y Pacto 87→92.

WITH partidos_homologados AS (
    SELECT
        ca.id AS partido_ca_id,
        ca.codpar AS codpar_ca,
        ca.nombre AS partido,
        COALESCE(
            (
                SELECT se.id
                FROM partidos AS se
                WHERE se.eleccion = 'SE'
                  AND se.codpar = CASE ca.codpar
                      WHEN '5' THEN '57'
                      WHEN '87' THEN '92'
                      ELSE ca.codpar
                  END
                LIMIT 1
            ),
            (
                SELECT se.id
                FROM partidos AS se
                WHERE se.eleccion = 'SE'
                  AND se.nombre = ca.nombre
                LIMIT 1
            )
        ) AS partido_se_id
    FROM partidos AS ca
    WHERE ca.eleccion = 'CA'
),
ca_candidato_municipio AS (
    SELECT
        mu.id AS municipio_id,
        c.id AS candidato_id,
        c.nombre AS candidato,
        c.partido_id AS partido_ca_id,
        SUM(rc.votos) AS votos_ca_candidato
    FROM resultados_candidato AS rc
    JOIN candidatos AS c
        ON c.id = rc.candidato_id
    JOIN partidos AS par
        ON par.id = c.partido_id
       AND par.eleccion = 'CA'
    JOIN mesas AS m
        ON m.id = rc.mesa_id
    JOIN puestos AS p
        ON p.id = m.puesto_id
    JOIN municipios AS mu
        ON mu.id = p.municipio_id
    WHERE c.codcan <> '0'
      AND c.nombre <> 'SOLO POR LA LISTA'
    GROUP BY
        mu.id,
        c.id,
        c.nombre,
        c.partido_id
),
ca_partido_municipio AS (
    SELECT
        mu.id AS municipio_id,
        rp.partido_id AS partido_ca_id,
        SUM(rp.votos) AS votos_ca_partido
    FROM resultados_partido AS rp
    JOIN partidos AS par
        ON par.id = rp.partido_id
       AND par.eleccion = 'CA'
    JOIN mesas AS m
        ON m.id = rp.mesa_id
    JOIN puestos AS p
        ON p.id = m.puesto_id
    JOIN municipios AS mu
        ON mu.id = p.municipio_id
    GROUP BY
        mu.id,
        rp.partido_id
),
se_partido_municipio AS (
    SELECT
        mu.id AS municipio_id,
        rp.partido_id AS partido_se_id,
        SUM(rp.votos) AS votos_se_partido
    FROM resultados_partido AS rp
    JOIN partidos AS par
        ON par.id = rp.partido_id
       AND par.eleccion = 'SE'
    JOIN mesas AS m
        ON m.id = rp.mesa_id
    JOIN puestos AS p
        ON p.id = m.puesto_id
    JOIN municipios AS mu
        ON mu.id = p.municipio_id
    GROUP BY
        mu.id,
        rp.partido_id
),
atribucion_municipio AS (
    SELECT
        cc.municipio_id,
        cc.candidato_id,
        cc.candidato,
        ph.codpar_ca,
        ph.partido,
        cc.votos_ca_candidato,
        cp.votos_ca_partido,
        sp.votos_se_partido,
        CAST(cc.votos_ca_candidato AS REAL)
            / NULLIF(cp.votos_ca_partido, 0)
            * sp.votos_se_partido AS atribucion_se
    FROM ca_candidato_municipio AS cc
    JOIN ca_partido_municipio AS cp
        ON cp.municipio_id = cc.municipio_id
       AND cp.partido_ca_id = cc.partido_ca_id
    JOIN partidos_homologados AS ph
        ON ph.partido_ca_id = cc.partido_ca_id
       AND ph.partido_se_id IS NOT NULL
    JOIN se_partido_municipio AS sp
        ON sp.municipio_id = cc.municipio_id
       AND sp.partido_se_id = ph.partido_se_id
    WHERE cp.votos_ca_partido > 0
)
SELECT
    candidato,
    codpar_ca,
    partido,
    SUM(votos_ca_candidato) AS votos_ca_candidato,
    SUM(votos_ca_partido) AS votos_ca_partido,
    SUM(votos_se_partido) AS votos_se_partido,
    ROUND(SUM(atribucion_se), 2) AS atribucion_se_consolidada
FROM atribucion_municipio
GROUP BY
    candidato_id,
    candidato,
    codpar_ca,
    partido
ORDER BY
    atribucion_se_consolidada DESC,
    votos_ca_candidato DESC
LIMIT 5;
