-- Reto 3.1 — Arrastre Alianza Verde Cámara → Senado
-- Homologación exigida: codpar_CA = 5 y codpar_SE = 57.
-- Unidad de análisis: puesto electoral dentro de cada municipio.

WITH votos_verdes AS (
    SELECT
        mu.nombre AS municipio,
        p.codigo AS puesto_codigo,
        p.nombre AS puesto,
        SUM(
            CASE
                WHEN par.eleccion = 'CA' AND par.codpar = '5'
                THEN rp.votos ELSE 0
            END
        ) AS votos_ca_verde,
        SUM(
            CASE
                WHEN par.eleccion = 'SE' AND par.codpar = '57'
                THEN rp.votos ELSE 0
            END
        ) AS votos_se_verde
    FROM resultados_partido AS rp
    JOIN partidos AS par
        ON par.id = rp.partido_id
    JOIN mesas AS m
        ON m.id = rp.mesa_id
    JOIN puestos AS p
        ON p.id = m.puesto_id
    JOIN municipios AS mu
        ON mu.id = p.municipio_id
    WHERE
        (par.eleccion = 'CA' AND par.codpar = '5')
        OR
        (par.eleccion = 'SE' AND par.codpar = '57')
    GROUP BY
        mu.nombre,
        p.codigo,
        p.nombre
)
SELECT
    municipio,
    puesto_codigo,
    puesto,
    votos_ca_verde,
    votos_se_verde,
    ROUND(
        CAST(votos_se_verde AS REAL) / NULLIF(votos_ca_verde, 0),
        4
    ) AS ratio_arrastre
FROM votos_verdes
WHERE votos_ca_verde > 0 OR votos_se_verde > 0
ORDER BY
    municipio,
    ratio_arrastre DESC,
    puesto;
