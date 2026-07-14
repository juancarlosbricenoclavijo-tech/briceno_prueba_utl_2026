PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS municipios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT NOT NULL UNIQUE,
    nombre TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS puestos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    municipio_id INTEGER NOT NULL,
    codigo TEXT NOT NULL UNIQUE,
    nombre TEXT NOT NULL,
    zona TEXT NOT NULL,
    mesas_esperadas INTEGER NOT NULL CHECK (mesas_esperadas >= 0),
    FOREIGN KEY (municipio_id) REFERENCES municipios(id)
);

CREATE TABLE IF NOT EXISTS mesas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    puesto_id INTEGER NOT NULL,
    numero INTEGER NOT NULL CHECK (numero > 0),
    codigo TEXT NOT NULL UNIQUE,
    FOREIGN KEY (puesto_id) REFERENCES puestos(id),
    UNIQUE (puesto_id, numero)
);

CREATE TABLE IF NOT EXISTS partidos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    eleccion TEXT NOT NULL CHECK (eleccion IN ('CA', 'SE')),
    codpar TEXT NOT NULL,
    nombre TEXT NOT NULL,
    UNIQUE (eleccion, codpar)
);

CREATE TABLE IF NOT EXISTS candidatos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    partido_id INTEGER NOT NULL,
    codcan TEXT NOT NULL,
    cedula TEXT,
    nombre TEXT NOT NULL,
    nombre_normalizado TEXT NOT NULL,
    FOREIGN KEY (partido_id) REFERENCES partidos(id),
    UNIQUE (partido_id, codcan)
);

CREATE TABLE IF NOT EXISTS totales_mesa (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mesa_id INTEGER NOT NULL,
    eleccion TEXT NOT NULL CHECK (eleccion IN ('CA', 'SE')),
    censo INTEGER NOT NULL DEFAULT 0,
    votantes INTEGER NOT NULL DEFAULT 0,
    abstencion INTEGER NOT NULL DEFAULT 0,
    votos_nulos INTEGER NOT NULL DEFAULT 0,
    votos_no_marcados INTEGER NOT NULL DEFAULT 0,
    votos_blancos INTEGER NOT NULL DEFAULT 0,
    votos_validos INTEGER NOT NULL DEFAULT 0,
    mesas_escrutadas INTEGER NOT NULL DEFAULT 0,
    fuente_url TEXT NOT NULL,
    FOREIGN KEY (mesa_id) REFERENCES mesas(id),
    UNIQUE (mesa_id, eleccion)
);

CREATE TABLE IF NOT EXISTS resultados_partido (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mesa_id INTEGER NOT NULL,
    partido_id INTEGER NOT NULL,
    votos INTEGER NOT NULL CHECK (votos >= 0),
    FOREIGN KEY (mesa_id) REFERENCES mesas(id),
    FOREIGN KEY (partido_id) REFERENCES partidos(id),
    UNIQUE (mesa_id, partido_id)
);

CREATE TABLE IF NOT EXISTS resultados_candidato (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mesa_id INTEGER NOT NULL,
    candidato_id INTEGER NOT NULL,
    votos INTEGER NOT NULL CHECK (votos >= 0),
    FOREIGN KEY (mesa_id) REFERENCES mesas(id),
    FOREIGN KEY (candidato_id) REFERENCES candidatos(id),
    UNIQUE (mesa_id, candidato_id)
);

CREATE TABLE IF NOT EXISTS carga_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha_carga TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fuente TEXT NOT NULL,
    eleccion TEXT NOT NULL CHECK (eleccion IN ('CA', 'SE')),
    municipio TEXT NOT NULL,
    solicitudes INTEGER NOT NULL DEFAULT 0,
    filas_insertadas INTEGER NOT NULL DEFAULT 0,
    filas_omitidas INTEGER NOT NULL DEFAULT 0,
    errores INTEGER NOT NULL DEFAULT 0,
    estado TEXT NOT NULL,
    detalle TEXT
);

CREATE INDEX IF NOT EXISTS idx_puestos_municipio
    ON puestos (municipio_id);

CREATE INDEX IF NOT EXISTS idx_mesas_puesto
    ON mesas (puesto_id, numero);

CREATE INDEX IF NOT EXISTS idx_resultados_partido_mesa
    ON resultados_partido (mesa_id, partido_id);

CREATE INDEX IF NOT EXISTS idx_resultados_candidato_mesa
    ON resultados_candidato (mesa_id, candidato_id);

CREATE INDEX IF NOT EXISTS idx_partidos_eleccion_codigo
    ON partidos (eleccion, codpar);

CREATE INDEX IF NOT EXISTS idx_candidatos_nombre_normalizado
    ON candidatos (nombre_normalizado);
