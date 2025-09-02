<!-- Selector de idioma -->
[English](README.md) | [Türkçe](README.tr.md) | [Español](README.es.md) | [Русский](README.ru.md)

# MiPower

MiPower es una integración personalizada (custom integration) para Home Assistant que permite encender un **Mi Box S** mediante el emparejamiento por Bluetooth (usando `bluetoothctl`). El Mi Box S no incluye un receptor de control remoto por infrarrojos (IR) como otros modelos Mi Box; por ello, este modelo solo puede controlarse de forma fiable mediante su mando Bluetooth. MiPower implementa una solución práctica para la limitación del modo de suspensión profunda del dispositivo.

**Por qué existe este proyecto:**  
Apagar un Mi Box S se puede hacer con un comando ADB, pero encenderlo solo es posible con el mando físico, porque el dispositivo entra en modo de suspensión profunda. Esta integración utiliza la secuencia de emparejamiento de `bluetoothctl` para despertar el dispositivo de forma remota — una solución pragmática que ayuda a controlar Mi Box S desde Home Assistant sin el mando original.

---

## Funcionalidades
- Proporciona una entidad tipo switch en Home Assistant que intenta despertar el Mi Box S mediante un intento controlado de emparejamiento Bluetooth.
- Configuración simple desde la interfaz (dirección MAC + nombre amigable).
- Compatible con HACS como integración personalizada.
- Incluye traducciones en inglés y turco; se pueden añadir más idiomas.

---

## Compatibilidad y Requisitos
- SO host: Linux con BlueZ (por ejemplo, Raspberry Pi OS). `bluetoothctl` debe estar disponible.
- Home Assistant debe ejecutarse en un host/contenedor con acceso al interfaz Bluetooth del host y a DBus (BlueZ). En instalaciones en contenedores puede ser necesario montar `/run/dbus` y otorgar permisos a dispositivos.
- Dependencia Python declarada en `manifest.json`: **pexpect** (utilizado para controlar sesiones `bluetoothctl`).
- Versión mínima de Home Assistant según metadatos: **2021.12.0**.
- Dominio de la integración: `mibox_socket` (archivos bajo `custom_components/mibox_socket`).

---

## Instalación

Se proporcionan dos métodos de instalación. Los archivos deben situarse en `custom_components/mibox_socket`.

### 1) Instalación manual (copiar archivos)
1. Crear el directorio: `config/custom_components/mibox_socket`
2. Copiar todos los archivos del directorio `custom_components/mibox_socket` de este repositorio al directorio creado, preservando la estructura (`translations/`, `manifest.json`, `switch.py`, `config_flow.py`, `__init__.py`, `const.py`, etc.).
3. Asegurarse de que `bluetoothctl` esté instalado en el host y que Home Assistant tenga acceso a DBus.
4. Reiniciar Home Assistant.

> Tras reiniciar, continúe con la sección **Configuración** abajo para añadir la integración en la UI.

### 2) Instalación vía HACS (recomendado)
1. Abra Home Assistant → **HACS** → **Integrations**.
	![HACS pantalla principal](docs/images/hacs_main.png)  
	*Vista principal de Integraciones en HACS.*

2. Haga clic en el menú de tres puntos → **Custom repositories**.
	![HACS repositorios personalizados](docs/images/hacs_custom_repos.png)  
	*Acceda al diálogo “Custom repositories” desde el menú de tres puntos.*

3. Añada el repositorio:
   - URL del repositorio: `https://github.com/DenizOner/MiPower`
   - Categoría / Tipo: **Integration**
   	![HACS añadir repo](docs/images/hacs_add_repo.png)  
	*Agregue la URL del repositorio y seleccione “Integration” como tipo.*

4. Tras indexar el repositorio, vaya a **HACS → Integrations**, busque **MiPower** e instálelo.
	![HACS instalar integración](docs/images/hacs_install_integration.png)  
	*Instale la integración MiPower desde HACS → Integrations.*

5. Reinicie Home Assistant si se le solicita.

> Tras reiniciar, continúe con la sección **Configuración** abajo.

---

## Configuración (post-instalación)
1. En Home Assistant vaya a **Settings → Devices & Services**.
	![Ajustes → Dispositivos y Servicios](docs/images/settings_devices_services.png)  
	*Abra Devices & Services (Dispositivos y Servicios) para añadir la integración.*

2. Haga clic en **Add Integration**.
	![Botón Añadir integración](docs/images/add_integration_button.png)  
	*Pulse el botón “Add Integration” (la ubicación del botón varía según la versión de HA).*

3. Busque **MiPower** y selecciónelo.
	![Campo de búsqueda](docs/images/search_mipower.png)  
	*Campo de búsqueda: escriba el nombre de la integración.*

4. Complete el formulario de configuración:
   - **MAC address** (requerido): la MAC Bluetooth de su Mi Box S (`XX:XX:XX:XX:XX:XX`).
   - **Friendly name** (requerido): etiqueta para la entidad switch.
   - **Opcional**: seleccione una entidad `media_player` existente para enlazar la integración, si lo desea.
   ![Formulario de configuración MiPower](docs/images/mipower_config_form.png)  
	*Ingrese la MAC del dispositivo en formato `AA:BB:CC:DD:EE:FF`, asigne un nombre amigable y envíe.*

5. Envíe. Aparecerá una nueva entidad switch (por ejemplo `switch.<friendly_name>`).

---

## Cómo funciona
- Al activar el switch MiPower, la integración inicia un intento de emparejamiento `bluetoothctl` hacia la MAC del Mi Box S mediante una sesión controlada (dirigida por `pexpect`). El intento de emparejamiento actúa como señal de despertar.
- Se trata de una solución temporal para el modo de suspensión profunda del dispositivo y no modifica el firmware ni la configuración del dispositivo.

---

## Notas de uso y buenas prácticas
- Compruebe que el adaptador Bluetooth del host funcione (`sudo bluetoothctl`).
- El Mi Box S debe estar dentro del alcance; las condiciones RF pueden afectar el éxito.
- Evite enviar comandos de emparejamiento de forma repetida y rápida.
- La integración no cambia el firmware del dispositivo; solo realiza un intento de emparejamiento como acción de despertar.

---

## Solución de problemas
- Verifique el formato de la dirección MAC.
- Compruebe que BlueZ y `bluetoothctl` puedan descubrir/conectar dispositivos en el host.
- Revise los logs de Home Assistant relacionados con `mibox_socket` (aumente el nivel de logs a debug si es necesario).
- Si usa contenedores, asegúrese de montar `/run/dbus` y conceder permisos.

---

## Contribuciones
Se aceptan contribuciones:
- Abra un Issue para errores o solicitudes de funciones.
- Haga fork del repositorio, implemente cambios en una rama y abra un Pull Request.
- Documente los cambios y agregue pasos de prueba si corresponde.

---

## Comentarios y Soporte
Use GitHub Issues para informes y sugerencias. Indique versión de Home Assistant, tipo de instalación, SO host, versión de BlueZ, logs relevantes y los pasos que realizó.

---

## Seguridad y Privacidad
- MiPower realiza intentos locales de emparejamiento Bluetooth y no transmite datos personales hacia el exterior.
- La integración requiere acceso a Bluetooth/DBus a nivel de host; úsela en hosts de confianza.

---

## Licencia
Este proyecto se publica en el dominio público bajo la **Creative Commons CC0 1.0 Universal (CC0 1.0)**. Puede copiar, modificar y distribuir libremente el trabajo.
Referencia: https://creativecommons.org/publicdomain/zero/1.0/

---

## Agradecimientos y Origen
MiPower es un fork del proyecto `mibox_socket` de @frlequ — muchas ideas centrales y la implementación original se derivaron de dicho repositorio.
