-- ============================================================================
-- Script: limpieza_ventas.sql
-- Descripcion: Pipeline de limpieza de datos de ventas
-- Fuente: DEV_DB.DEVIN_TEST.RAW_SALES_DATA
-- Destino: DEV_DB.DEVIN_TEST.VENTAS_LIMPIAS
-- ============================================================================
--
-- Problemas detectados en RAW_SALES_DATA:
--   1. Nombres de clientes con formato inconsistente (mezcla de mayusculas
--      y minusculas, p.ej. 'alvaro lopez' vs 'ALVARO LOPEZ')
--   2. Importes negativos que representan registros erroneos
--
-- Transformaciones aplicadas:
--   - UPPER(CLIENTE): normaliza todos los nombres a MAYUSCULAS
--   - WHERE IMPORTE >= 0: filtra importes negativos
-- ============================================================================

USE DATABASE DEV_DB;
USE SCHEMA DEVIN_TEST;

CREATE OR REPLACE TABLE DEV_DB.DEVIN_TEST.VENTAS_LIMPIAS AS
SELECT
    ID,
    UPPER(CLIENTE) AS CLIENTE,
    IMPORTE,
    FECHA,
    ESTADO
FROM DEV_DB.DEVIN_TEST.RAW_SALES_DATA
WHERE IMPORTE >= 0
ORDER BY ID;
