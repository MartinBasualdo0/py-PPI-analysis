[Saltar al contenido principal](https://pypi.org/project/py-ppi-arg/#content) **Join us at PyCon US 2026 in Long Beach, CA starting May 13! Grab your ticket today before they're gone. ** [PYCON US: TICKET SALES ENDING SOON!](https://us.pycon.org/2026/attend/information/)

[![PyPI](https://pypi.org/static/images/logo-small.8998e9d1.svg)](https://pypi.org/)

Buscar en PyPI[ ] Buscar

* [Ayuda](https://pypi.org/help/)
* [Docs](https://docs.pypi.org/)
* [Patrocinadores](https://pypi.org/sponsors/)
* [Acceder](https://pypi.org/account/login/?next=https%3A%2F%2Fpypi.org%2Fproject%2Fpy-ppi-arg%2F)
* [Registrarse](https://pypi.org/account/register/)

# py-ppi-arg 0.1.10

pip install py-ppi-arg**Copiar instrucciones para PIP**

[Versión más reciente](https://pypi.org/project/py-ppi-arg/)Publicación: 3 ago 2025

Python connector for PortfolioPersonals's Rest APIs.

### Navegación

* [ Descripción de proyecto](https://pypi.org/project/py-ppi-arg/#description)
* [ Histórico de versiones](https://pypi.org/project/py-ppi-arg/#history)
* [ Archivos de descarga](https://pypi.org/project/py-ppi-arg/#files)

### Verified details

*These details have been [verified by PyPI](https://docs.pypi.org/project_metadata/#verified-details)*###### Responsables

[![Avatar de MartinBasualdo0 de gravatar.com](https://pypi-camo.freetls.fastly.net/473028abcfa7cc0826e331fdcbb5698f41cf4933/68747470733a2f2f7365637572652e67726176617461722e636f6d2f6176617461722f32633633383334366338333662663537313131376538383438643430663336643f73697a653d3530 "Avatar de MartinBasualdo0 de gravatar.com") **MartinBasualdo0**](https://pypi.org/user/MartinBasualdo0/)

### Unverified details

*These details have **not** been verified by PyPI*###### Enlaces del proyecto

* [Homepage](https://github.com/MartinBasualdo0/pyPPI)

###### Metainformación

* **Licencia:** MIT License
* **Autor:** [Martin Basualdo](mailto:martin.basualdo@hotmail.com)

###### Clasificadores

* **Development Status**
  * [4 - Beta](https://pypi.org/search/?c=Development+Status+%3A%3A+4+-+Beta)
* **Intended Audience**
  * [Developers](https://pypi.org/search/?c=Intended+Audience+%3A%3A+Developers)
  * [Information Technology](https://pypi.org/search/?c=Intended+Audience+%3A%3A+Information+Technology)
  * [Science/Research](https://pypi.org/search/?c=Intended+Audience+%3A%3A+Science%2FResearch)
* **License**
  * [OSI Approved :: MIT License](https://pypi.org/search/?c=License+%3A%3A+OSI+Approved+%3A%3A+MIT+License)
* **Operating System**
  * [OS Independent](https://pypi.org/search/?c=Operating+System+%3A%3A+OS+Independent)
* **Programming Language**
  * [Python :: 3](https://pypi.org/search/?c=Programming+Language+%3A%3A+Python+%3A%3A+3)
* **Topic**
  * [Office/Business :: Financial :: Investment](https://pypi.org/search/?c=Topic+%3A%3A+Office%2FBusiness+%3A%3A+Financial+%3A%3A+Investment)
  * [Software Development](https://pypi.org/search/?c=Topic+%3A%3A+Software+Development)

[![Sponsored: Python Software Foundation](https://media.ethicalads.io/images/2026/05/jetbrains_oy8RCvf_aVw55Sw.png)](https://server.ethicalads.io/proxy/click/9624/019e0d0f-0178-71c2-bbdd-e580ca77962b/)JetBrains is a Contributing sponsor of the Python Software Foundation.

*[PSF Sponsor](https://www.python.org/psf/sponsorship/?ref=ethicalads-placement) · [Served ethically](https://www.ethicalads.io/sponsorship-platform/?ref=psf)*

[Report project as malware](https://pypi.org/project/py-ppi-arg/submit-malware-report/)

## Descripción de proyecto

# Welcome to py_ppi_arg' Documentation

## Overview

py_ppi_arg is a Python library that enables interaction with PortfolioPersonal REST APIs. It is designed to save developers hours of research and coding required to connect to PortfolioPersonal REST APIs.

## Disclaimer

py_ppi_arg is not owned by Portfolio Personal, and the authors are not responsible for the use of this library.

## Installation

To install py_ppi_arg, you can use the following command:

```
pip install py_ppi_arg
```

## API Credentials

To use this library, you need to have the correct authentication credentials.

## Dependencies

The library has the following dependency:

```
requests>=2.31.0
simplejson>=3.19.1
pyotp>=2.9.0
beautifulsoup4>=4.12.3
bs4>=0.0.2
certifi>=2024.7.4
charset-normalizer>=3.3.2
idna>=3.7
soupsieve>=2.5
urllib3>=2.2.2
```

## Features

#### Available Methods

#### Initialization

Before using the library, you need to initialize it with a valid email and password.

#### REST

The library provides functions to make requests to the REST API and retrieve the corresponding responses.

###### Functions

* **get_tickers_list** : Retrieves instruments quote list information filtered by instrument type, operation type and settlement.
* **search_tickers** : Queries the API to search for a particular instrument based on the name.
* **get_technical_data_bonds** : Retrieves the techical data for a bond.
* **get_historic_data** : Retrieves the historic data for an item.
* **get_intraday_data** : Retrieves the intraday data for an item.

> All functions return a dictionary representing the JSON response.

#### Enumerations

The library also provides enumerations to help developers avoid errors and improve readability.

* **Currency** : Identifies the available currencies in the app.
* **InstrumentTypes** : Identifies the instrument types.
* **OperationType** : Identifies the operation types.
* **Settlements** : Identifies the different settlement dates.

## Usage

Once the library has been installed, you can import and initialize it. The initialization sets the email and password. It then attempts to authenticate with the provided credentials. If the authentication fails, an `ApiException` is thrown.

```
from py_ppi_arg import PPI

app = PPI(email="sample@email.com", password="S4mp13.p4ssW0rd")
```

#### REST

```
# Get information about all the available bonds
app.get_tickers_list(
    instrument_type = app.instrument_types.PUBLIC_BOND,
    operation_type = app.operation_types.COMPRA,
    settlement = app.settlements.T2
)

# Get the technical data for a bond
app.get_technical_data_bonds(
        settlement=app.settlements.T2,
        item_id="804421"
        )

# Get the historic price data for an instrument
app.get_historic_data(item_id="261", settlement=app.settlements.T2)

# Get the information about for an instrument
app.search_tickers(short_ticker = "AL30")

```

For more information you can check this [article.](https://medium.com/@nachoherrera/biblioteca-pycocos-a3579721c79e)

## Official API Documentation

There is no official API documentation for this library. The library was created by webscraping the app.

## Acknowledgements

This library was created taking as an example the work of the Scrappers Argentinos and Inversiones y Algoritmos Telegram Groups in the [pyCocos ](https://pypi.org/project/pyCocos/)library.

@LucaGelmini and @patruccoluciano helped by giving feedback and suggestions for a better code. Special thanks to them.

![](https://pypi.org/static/images/white-cube.2351a86c.svg)

## Ayuda

* [Instalación de paquetes](https://packaging.python.org/tutorials/installing-packages/ "Enlace externo")
* [Carga de paquetes](https://packaging.python.org/tutorials/packaging-projects/ "Enlace externo")
* [Manual de uso](https://packaging.python.org/ "Enlace externo")
* [Retención de nombres de proyecto](https://www.python.org/dev/peps/pep-0541/ "Enlace externo")
* [Preguntas frecuentes](https://pypi.org/help/)

## Acerca de PyPI

* [PyPI Blog](https://blog.pypi.org/ "Enlace externo")
* [Cuadro de mando de infraestructura](https://dtdg.co/pypi "Enlace externo")
* [Estadísticas](https://pypi.org/stats/)
* [Logos y trademarks](https://pypi.org/trademarks/)
* [Nuestros patrocinadores](https://pypi.org/sponsors/)

## Contribuir con PyPI

* [Defectos y comentarios](https://pypi.org/help/#feedback)
* [Contribuir en GitHub](https://github.com/pypi/warehouse "Enlace externo")
* [Traducir PyPI](https://hosted.weblate.org/projects/pypa/warehouse/ "Enlace externo")
* [Patrocinar a PyPI](https://pypi.org/sponsors/)
* [Créditos de desarrollo](https://github.com/pypi/warehouse/graphs/contributors "Enlace externo")

## Uso de PyPI

* [Terms of Service](https://policies.python.org/pypi.org/Terms-of-Service/ "Enlace externo")
* [Informar de un problema de seguridad](https://pypi.org/security/)
* [Código de conducta](https://policies.python.org/python.org/code-of-conduct/ "Enlace externo")
* [Privacy Notice](https://policies.python.org/pypi.org/Privacy-Notice/ "Enlace externo")
* [Políticas de Uso Aceptable](https://policies.python.org/pypi.org/Acceptable-Use-Policy/ "Enlace externo")

---

Estado:[ All Systems Operational](https://status.python.org/ "Enlace externo")

Desarrollado y mantenido por la comunidad de Python para la comunidad de Python.
[¡Done hoy mismo!](https://donate.pypi.org/)

"PyPI", "Python Package Index", y los logos de los bloques son [marcas](https://pypi.org/trademarks/) registradas de [Python Software Foundation](https://www.python.org/psf-landing).

© 2026 [Python Software Foundation](https://www.python.org/psf-landing/ "Enlace externo")
[Mapa del sitio](https://pypi.org/sitemap/)

Deployed from [`19fa79f`](https://github.com/pypi/warehouse/commit/19fa79fa00df780ba837680399bdcc867fdd97cf "Enlace externo")

* English
* español
* français
* 日本語
* português (Brasil)
* українська
* Ελληνικά
* Deutsch
* 中文 (简体)
* 中文 (繁體)
* русский
* עברית
* Esperanto
* 한국어

[![](https://pypi-camo.freetls.fastly.net/ed7074cadad1a06f56bc520ad9bd3e00d0704c5b/68747470733a2f2f73746f726167652e676f6f676c65617069732e636f6d2f707970692d6173736574732f73706f6e736f726c6f676f732f6177732d77686974652d6c6f676f2d7443615473387a432e706e67)AWS**Cloud computing and Security Sponsor**](https://aws.amazon.com/)[![](https://pypi-camo.freetls.fastly.net/8855f7c063a3bdb5b0ce8d91bfc50cf851cc5c51/68747470733a2f2f73746f726167652e676f6f676c65617069732e636f6d2f707970692d6173736574732f73706f6e736f726c6f676f732f64617461646f672d77686974652d6c6f676f2d6668644c4e666c6f2e706e67)Datadog**Monitoring**](https://www.datadoghq.com/)[![](https://pypi-camo.freetls.fastly.net/60f709d24f3e4d469f9adc77c65e2f5291a3d165/68747470733a2f2f73746f726167652e676f6f676c65617069732e636f6d2f707970692d6173736574732f73706f6e736f726c6f676f732f6465706f742d77686974652d6c6f676f2d7038506f476831302e706e67)Depot**Continuous Integration**](https://depot.dev/)[![](https://pypi-camo.freetls.fastly.net/df6fe8829cbff2d7f668d98571df1fd011f36192/68747470733a2f2f73746f726167652e676f6f676c65617069732e636f6d2f707970692d6173736574732f73706f6e736f726c6f676f732f666173746c792d77686974652d6c6f676f2d65684d3077735f6f2e706e67)Fastly**CDN**](https://www.fastly.com/)[![](https://pypi-camo.freetls.fastly.net/420cc8cf360bac879e24c923b2f50ba7d1314fb0/68747470733a2f2f73746f726167652e676f6f676c65617069732e636f6d2f707970692d6173736574732f73706f6e736f726c6f676f732f676f6f676c652d77686974652d6c6f676f2d616734424e3774332e706e67)Google**Download Analytics**](https://careers.google.com/)[![](https://pypi-camo.freetls.fastly.net/d01053c02f3a626b73ffcb06b96367fdbbf9e230/68747470733a2f2f73746f726167652e676f6f676c65617069732e636f6d2f707970692d6173736574732f73706f6e736f726c6f676f732f70696e67646f6d2d77686974652d6c6f676f2d67355831547546362e706e67)Pingdom**Monitoring**](https://www.pingdom.com/)[![](https://pypi-camo.freetls.fastly.net/67af7117035e2345bacb5a82e9aa8b5b3e70701d/68747470733a2f2f73746f726167652e676f6f676c65617069732e636f6d2f707970692d6173736574732f73706f6e736f726c6f676f732f73656e7472792d77686974652d6c6f676f2d4a2d6b64742d706e2e706e67)Sentry**Error logging**](https://sentry.io/for/python/?utm_source=pypi&utm_medium=paid-community&utm_campaign=python-na-evergreen&utm_content=static-ad-pypi-sponsor-learnmore)[![](https://pypi-camo.freetls.fastly.net/b611884ff90435a0575dbab7d9b0d3e60f136466/68747470733a2f2f73746f726167652e676f6f676c65617069732e636f6d2f707970692d6173736574732f73706f6e736f726c6f676f732f737461747573706167652d77686974652d6c6f676f2d5467476c6a4a2d502e706e67)StatusPage**Status page**](https://statuspage.io/)
