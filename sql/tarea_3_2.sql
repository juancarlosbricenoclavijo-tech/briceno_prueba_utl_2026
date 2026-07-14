-- Reto 3.2 — Dominancia extrema
-- Mesas en las que una candidatura individual concentra más del 60 %
-- de los votos de su partido. Se excluye "SOLO POR LA LISTA" (codcan = 0).

SELECT
    mu.nombre AS municipio,
    p.codigo AS puesto_codigo,
    p.nombre AS puesto,
    m.numero AS mesa,
    par.eleccion,
    par.codpar,
    par.nombre AS partido,
    c.codcan,
    c.nombre AS candidato,
    rc.votos AS votos_candidato,
    rp.votos AS votos_partido,
    ROUND(
        100.0 * rc.votos / NULLIF(rp.votos, 0),
        2
    ) AS porcentaje_dominancia
FROM resultados_candidato AS rc
JOIN candidatos AS c
    ON c.id = rc.candidato_id
JOIN partidos AS par
    ON par.id = c.partido_id
JOIN resultados_partido AS rp
    ON rp.mesa_id = rc.mesa_id
   AND rp.partido_id = par.id
JOIN mesas AS m
    ON m.id = rc.mesa_id
JOIN puestos AS p
    ON p.id = m.puesto_id
JOIN municipios AS mu
    ON mu.id = p.municipio_id
WHERE
    c.codcan <> '0'
    AND c.nombre <> 'SOLO POR LA LISTA'
    AND rp.votos > 0
    AND CAST(rc.votos AS REAL) / rp.votos > 0.60
ORDER BY
    porcentaje_dominancia DESC,
    votos_candidato DESC,
    municipio,
    puesto,
    mesa;
