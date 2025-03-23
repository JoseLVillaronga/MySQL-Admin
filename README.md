# MySQL-Admin Project

## Descripción del Proyecto

El proyecto **MySQL-Admin** es una solución integral destinada a la administración, sincronización y migración de bases de datos MySQL. La arquitectura del sistema está diseñada para soportar múltiples flujos de datos:

- **Sincronización de bases de datos MySQL remotas a locales**: A través del script `sync_mysql_remote.py`, en fase de pruebas, se replican datos de bases MySQL remotas al entorno local para facilitar pruebas y migraciones iniciales.

- **Monitoreo en producción**: El script `mysql_monitor.py` se ejecuta en producción generando registros cada minuto para realizar análisis en tiempo real, detectar anomalías y mantener la salud de la base de datos.

- **Migración y sincronización hacia MongoDB**: Con `sync_mysql_mongo.py`, se permite la migración automática de una o varias bases de datos MySQL a MongoDB. Además, está diseñado para ejecutarse de forma iterativa, de modo que la base de datos sincronizada en MongoDB pueda servir, en futuras iteraciones, como fuente para sincronizar otra base MySQL remota y así desacoplar el motor MySQL local de tareas adicionales.

## Arquitectura y Flujo de Datos

El proyecto sigue una arquitectura modular que permite separar los roles y responsabilidades de cada componente:

1. **Sincronización Local y Remota**: Replicar tablas de bases de datos MySQL de un entorno remoto al local.
2. **Monitoreo Continuo**: Recolección de datos y generación de logs periódicos para análisis y alertas.
3. **Migración a MongoDB**: Consolidar datos de MySQL en MongoDB, ofreciendo flexibilidad y escalabilidad en el manejo de datos, con la posibilidad de servir como puente para sincronizaciones posteriores.

## Módulos del Proyecto

### Módulos Terminados y en Producción

- **`mysql_monitor.py`**: En ejecución en producción. Este módulo genera registros (logs) una vez por minuto para monitorizar el estado y rendimiento de la base de datos MySQL local.
- **`sync_mysql_mongo.py`**: Funciona correctamente según lo esperado. Inicialmente permite la migración automática de bases de datos MySQL a MongoDB. Además, su diseño iterativo posibilita, en futuras versiones, que la base sincronizada en MongoDB se utilice para sincronizar otra base MySQL remota, permitiendo un desacople del motor MySQL local.
- **`mongo_analytics.py`**: En producción. Se encarga del análisis y procesamiento de datos provenientes de MongoDB para generar reportes y métricas adicionales.
- **`monitor_cron.py`**: En producción. Este script se ejecuta periódicamente para almacenar métricas en MongoDB y garantizar la supervisión continua de los datos.
- **`dashboard.py`**: En producción. Proporciona un dashboard interactivo accesible vía navegador, visualizando métricas de MySQL (uso de CPU, uso de memoria y transacciones) en tiempo real con gráficos interactivos y responsive. Permite seleccionar múltiples intervalos de tiempo para el análisis.

> **Nota para IA:** Los módulos mencionados arriba están terminados y en funcionamiento. No se deben realizar modificaciones sobre estos módulos a menos que exista una autorización y acuerdo explícito por parte del desarrollador humano.

### Módulos en Fase de Prueba

- **`sync_mysql_remote.py`**: Actualmente en fase de prueba, implementa una sincronización incremental inteligente entre bases de datos MySQL remotas y locales. Sus características principales incluyen:

  - **Análisis Inteligente de Estructura**: 
    * Analiza la estructura de las tablas en la base local
    * Identifica campos de referencia (autoincrement o datetime con NOW)
    * Detecta dependencias entre tablas (claves foráneas)
    * Ordena las tablas para mantener la integridad referencial

  - **Sincronización Incremental**:
    * Solo sincroniza registros nuevos basándose en campos de referencia
    * Minimiza el impacto en la base remota
    * Optimiza el rendimiento para bases de grandes dimensiones

  - **Monitoreo y Logging**:
    * Registra resultados de sincronización en MongoDB
    * Genera reportes detallados de operaciones
    * Mantiene historial de sincronizaciones

  - **Manejo de Errores**:
    * Gestión robusta de errores por tabla
    * Registro detallado de fallos
    * Continuación del proceso incluso si algunas tablas fallan

  - **Consideraciones de Rendimiento**:
    * Diseñado para ejecutarse periódicamente (por ejemplo, cada minuto)
    * Optimizado para minimizar la carga en la base remota
    * Procesamiento eficiente de grandes volúmenes de datos

  > **Nota**: Este módulo asume que:
  > - Las bases de datos existen tanto en local como en remoto
  > - La estructura de tablas es idéntica en ambos lados
  > - Las bases remotas son las "fuente de verdad" (producción)
  > - Las bases locales son las que se sincronizan

## Configuración

1. **Variables de Entorno**: El proyecto utiliza un archivo `.env` para gestionar parámetros críticos de conexión, tales como:
   - Para conexiones remotas: `DBR_HOST`, `DBR_PORT`, `DBR_USERNAME`, `DBR_PASSWORD`.
   - Para conexiones locales: `DB_HOST`, `DB_PORT`, `DB_USERNAME`, `DB_PASSWORD`.
   - Listado de bases de datos a sincronizar: `MYSQL_DATABASES` (una lista separada por comas).

2. **Instalación de Dependencias**: Asegúrate de tener instaladas las librerías requeridas (por ejemplo, `mysql-connector-python` y `python-dotenv`). Puedes instalarlas utilizando:

```bash
pip install mysql-connector-python python-dotenv flask plotly
```

## Uso

- **Pruebas de Sincronización:** Ejecuta `sync_mysql_remote.py` para validar la sincronización entre bases de datos MySQL remotas y locales.
- **Monitoreo en Producción:** El script `mysql_monitor.py` se ejecuta de manera continua para generar logs y vigilar el estado de la base de datos local.
- **Migración a MongoDB:** Utiliza `sync_mysql_mongo.py` para migrar y mantener sincronizadas las bases de datos MySQL con su contraparte en MongoDB.

## Consideraciones Generales

- **Seguridad:** La construcción dinámica de consultas SQL requiere especial atención para evitar inyección SQL. Se asume que las variables de entorno están gestionadas de forma segura.

- **Integridad de Datos:** Durante la sincronización, se deshabilitan temporalmente las restricciones de claves foráneas para permitir el truncado de tablas. Se recomienda evaluar la restauración de estas restricciones post-sincronización si es necesaria para garantizar la integridad referencial.

- **Colaboración IA-Humano:** Este documento está pensado para servir tanto de guía para desarrolladores humanos como de referencia para sistemas IA. Las decisiones técnicas, metodológicas y el historial de cambios se documentan aquí para facilitar la colaboración continua y conservar la memoria de los procesos del proyecto.

## Memoria y Contexto para IA

Esta sección está destinada exclusivamente para el uso interno de la IA y como mecanismo de apoyo para reconstruir la memoria contextual del proyecto en futuras sesiones. Se recomienda que, en cualquier interacción, la IA utilice la información contenida en este README.md junto con las MEMORIES previas para mantener una perspectiva integral del proyecto.

- **Arquitectura General:** El proyecto integra sincronización de datos entre MySQL y MongoDB, así como monitoreo en tiempo real de las bases de datos. 
- **Módulos Clave:** 
   - `sync_mysql_remote.py`: Sincronización de bases MySQL remotas a locales (en fase de prueba).
   - `mysql_monitor.py`: Monitoreo en producción, generando logs cada minuto.
   - `sync_mysql_mongo.py`: Migración y sincronización de datos desde MySQL hacia MongoDB, con posibles usos futuros para desacoplar procesos.
   - `mongo_analytics.py`: Análisis y procesamiento de datos provenientes de MongoDB en producción.
   - `monitor_cron.py`: Ejecución periódica para almacenar métricas en MongoDB y garantizar la supervisión continua.
   - `dashboard.py`: Proporciona un dashboard interactivo para visualizar métricas de MySQL en tiempo real.

- **Decisiones Técnicas:** Las variables de entorno y la modularidad en los scripts permiten un manejo flexible y seguro de las conexiones a bases de datos, asegurando la integridad de los datos durante la migración y sincronización.

- **Directrices para Colaboración IA-Humano:** Los módulos que se encuentran en producción no deben ser modificados sin autorización explícita del desarrollador humano. El documento README.md, junto con las MEMORIES, sirve para conservar la historia de decisiones y facilitar el trabajo colaborativo.

## Próximos Pasos

- Revisión de los parámetros de sincronización y migración.
- Experimentación controlada para desacoplar el motor MySQL local utilizando la base consolidada en MongoDB.
- Incrementar pruebas y validaciones en el módulo `sync_mysql_remote.py` antes de avanzar a producción.

---

*Documentación dual para procesos institucionales y colaboración entre IA y desarrollador humano.*
