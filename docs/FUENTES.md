# Fuentes configuradas

> Generado con `python herramientas/generar_doc_fuentes.py`.
> La verdad está en `config/fuentes/*.yaml`.

**Total: 141 fuentes** — 61 RSS y 80 páginas de Facebook.

Las 80 páginas de Facebook se reparten en grupos de 2, o sea **40 grupos de CI** por corrida (tope del planificador: 40; el workflow limita la concurrencia por separado).

`peso` (1-5) decide qué versión gana cuando varios medios traen la misma historia, y suma a la importancia del item.

## Agencias y organismos internacionales

`config/fuentes/agencias.yaml` — 6 fuentes

| id | nombre | tema | región | idioma | peso |
|---|---|---|---|---|---|
| `rss_ap_top` | [The Associated Press](https://rsshub.app/apnews/topics/apf-topnews) | mundo | Global | en | 5 |
| `rss_efe_portada` | [Agencia EFE](https://efe.com/feed/) | mundo | Global | es | 5 |
| `rss_reliefweb` | [ReliefWeb - Emergencias](https://reliefweb.int/updates/rss.xml) | mundo | Global | en | 4 |
| `rss_un_news` | [UN News](https://news.un.org/feed/subscribe/en/news/all/rss.xml) | mundo | Global | en | 5 |
| `rss_un_noticias_es` | [Noticias ONU](https://news.un.org/feed/subscribe/es/news/all/rss.xml) | mundo | Global | es | 5 |
| `rss_who` | [World Health Organization](https://www.who.int/rss-feeds/news-english.xml) | salud | Global | en | 5 |

## Páginas públicas de Facebook

`config/fuentes/facebook.yaml` — 80 fuentes

| id | nombre | tema | región | idioma | peso |
|---|---|---|---|---|---|
| `fb_abc_news` | [ABC News](https://www.facebook.com/ABCNews/) | mundo | América del Norte | en | 4 |
| `fb_abya_yala` | [Abya Yala Tv](https://www.facebook.com/AbyaYalaTv/) | mundo | Bolivia | es | 3 |
| `fb_afp` | [AFP News Agency](https://www.facebook.com/AFPnewsenglish/) | mundo | Global | en | 4 |
| `fb_aljazeera` | [Al Jazeera English](https://www.facebook.com/aljazeera/) | mundo | Medio Oriente | en | 4 |
| `fb_anf` | [Agencia de Noticias Fides - ANF](https://www.facebook.com/ANFidesBolivia/) | mundo | Bolivia | es | 3 |
| `fb_ap` | [The Associated Press](https://www.facebook.com/APNews/) | mundo | Global | en | 5 |
| `fb_atb_digital` | [ATB Digital](https://www.facebook.com/ATBDigital/) | mundo | Bolivia | es | 4 |
| `fb_bbc_mundo` | [BBC News Mundo](https://www.facebook.com/bbcmundo/) | mundo | Global | es | 5 |
| `fb_bbc_news` | [BBC News](https://www.facebook.com/bbcnews/) | mundo | Global | en | 5 |
| `fb_bloomberg` | [Bloomberg](https://www.facebook.com/Bloomberg/) | economia | Global | en | 4 |
| `fb_bolivia_tv` | [Bolivia Tv Oficial](https://www.facebook.com/BTVCanalOficial/) | mundo | Bolivia | es | 4 |
| `fb_bolivia_verifica` | [Bolivia Verifica](https://www.facebook.com/BoliviaVerifica/) | mundo | Bolivia | es | 4 |
| `fb_bolivision` | [Noticias Bolivisión](https://www.facebook.com/NoticiasBolivision/) | mundo | Bolivia | es | 4 |
| `fb_brujula_digital` | [Brújula Digital Bolivia](https://www.facebook.com/brujuladigitalbolivia/) | mundo | Bolivia | es | 4 |
| `fb_c5n` | [C5N](https://www.facebook.com/C5N.Noticias/) | mundo | América Latina | es | 3 |
| `fb_cadena_a` | [Cadena A - Red Nacional](https://www.facebook.com/cadenaabolivia/) | mundo | Bolivia | es | 3 |
| `fb_cbc_news` | [CBC News](https://www.facebook.com/cbcnews/) | mundo | América del Norte | en | 4 |
| `fb_cbs_news` | [CBS News](https://www.facebook.com/CBSNews/) | mundo | América del Norte | en | 4 |
| `fb_clarin` | [Clarín](https://www.facebook.com/clarincom/) | mundo | América Latina | es | 3 |
| `fb_cnn` | [CNN](https://www.facebook.com/cnn/) | mundo | América del Norte | en | 4 |
| `fb_cnn_brasil` | [CNN Brasil](https://www.facebook.com/cnnbrasil/) | mundo | América Latina | pt | 4 |
| `fb_cnn_espanol` | [CNN en Español](https://www.facebook.com/cnnee/) | mundo | América Latina | es | 4 |
| `fb_correo_del_sur` | [Correo del Sur](https://www.facebook.com/correodelsur/) | mundo | Bolivia | es | 4 |
| `fb_cronica_tv` | [Crónica TV](https://www.facebook.com/cronicatelevision/) | mundo | América Latina | es | 3 |
| `fb_dw_espanol` | [DW Español](https://www.facebook.com/dw.espanol/) | mundo | Europa | es | 4 |
| `fb_economist` | [The Economist](https://www.facebook.com/TheEconomist/) | economia | Global | en | 4 |
| `fb_el_diario_bolivia` | [El Diario - Bolivia](https://www.facebook.com/eldiario.bolivia/) | mundo | Bolivia | es | 3 |
| `fb_el_pais_tarija` | [El País Tarija](https://www.facebook.com/elpais.bo/) | mundo | Bolivia | es | 3 |
| `fb_el_potosi` | [El Potosí](https://www.facebook.com/elpotosi.noticias/) | mundo | Bolivia | es | 3 |
| `fb_el_tiempo_col` | [EL TIEMPO](https://www.facebook.com/eltiempo/) | mundo | América Latina | es | 4 |
| `fb_eldeber` | [EL DEBER](https://www.facebook.com/GrupoELDEBER/) | mundo | Bolivia | es | 3 |
| `fb_elpais` | [El País](https://www.facebook.com/elpais/) | mundo | Europa | es | 4 |
| `fb_erbol` | [Periódico Digital ERBOL](https://www.facebook.com/ErbolDigital/) | mundo | Bolivia | es | 3 |
| `fb_espn` | [ESPN](https://www.facebook.com/espn/) | deportes | Global | en | 3 |
| `fb_estadao` | [Estadão](https://www.facebook.com/estadao/) | mundo | América Latina | pt | 4 |
| `fb_euronews_es` | [Euronews en Español](https://www.facebook.com/euronews.es/) | mundo | Europa | es | 3 |
| `fb_financial_times` | [Financial Times](https://www.facebook.com/financialtimes/) | economia | Global | en | 4 |
| `fb_folha` | [Folha de S.Paulo](https://www.facebook.com/folhadesp/) | mundo | América Latina | pt | 4 |
| `fb_france24_es` | [France 24 Español](https://www.facebook.com/France24.Espanol/) | mundo | Europa | es | 4 |
| `fb_g1_brasil` | [g1](https://www.facebook.com/g1/) | mundo | América Latina | pt | 4 |
| `fb_gigavision` | [RED Gigavisión Noticias](https://www.facebook.com/redgigavisionnoticias/) | mundo | Bolivia | es | 3 |
| `fb_globonews` | [GloboNews](https://www.facebook.com/GloboNews/) | mundo | América Latina | pt | 4 |
| `fb_guardian` | [The Guardian](https://www.facebook.com/theguardian/) | mundo | Europa | en | 4 |
| `fb_infobae` | [Infobae](https://www.facebook.com/infobae/) | mundo | América Latina | es | 3 |
| `fb_la_nacion_ar` | [LA NACION](https://www.facebook.com/lanacion/) | mundo | América Latina | es | 4 |
| `fb_la_patria` | [La Patria Bolivia](https://www.facebook.com/LaPatriaBolivia/) | mundo | Bolivia | es | 3 |
| `fb_los_tiempos` | [Los Tiempos Digital](https://www.facebook.com/lostiemposbol1/) | mundo | Bolivia | es | 4 |
| `fb_marca` | [Marca](https://www.facebook.com/MARCA/) | deportes | Global | es | 3 |
| `fb_meganoticias_chile` | [Meganoticias](https://www.facebook.com/meganoticiascl/) | mundo | América Latina | es | 3 |
| `fb_nasa` | [NASA](https://www.facebook.com/NASA/) | ciencia | Global | en | 4 |
| `fb_natgeo` | [National Geographic](https://www.facebook.com/natgeo/) | ciencia | Global | en | 3 |
| `fb_nbc_news` | [NBC News](https://www.facebook.com/NBCNews/) | mundo | América del Norte | en | 4 |
| `fb_noticias_caracol` | [Noticias Caracol](https://www.facebook.com/NoticiasCaracol/) | mundo | América Latina | es | 4 |
| `fb_noticias_rcn` | [Noticias RCN](https://www.facebook.com/NoticiasRCN/) | mundo | América Latina | es | 4 |
| `fb_npr` | [NPR](https://www.facebook.com/NPR/) | mundo | América del Norte | en | 4 |
| `fb_ntn24` | [NTN24](https://www.facebook.com/NTN24/) | mundo | América Latina | es | 4 |
| `fb_nytimes` | [The New York Times](https://www.facebook.com/nytimes/) | mundo | América del Norte | en | 4 |
| `fb_o_globo` | [O Globo](https://www.facebook.com/jornaloglobo/) | mundo | América Latina | pt | 4 |
| `fb_panamericana` | [Radio Panamericana](https://www.facebook.com/NoticiasPanamericana/) | mundo | Bolivia | es | 3 |
| `fb_pat_bolivia` | [PAT Bolivia](https://www.facebook.com/patboliviahd/) | mundo | Bolivia | es | 3 |
| `fb_perfil` | [Perfil](https://www.facebook.com/perfilcom/) | mundo | América Latina | es | 3 |
| `fb_politico` | [POLITICO](https://www.facebook.com/politico/) | politica | América del Norte | en | 4 |
| `fb_radio_companera` | [Radio Compañera 106.3](https://www.facebook.com/radiocompanera106.3/) | mundo | Bolivia | es | 3 |
| `fb_radio_fides` | [Radio Fides de Bolivia](https://www.facebook.com/RadioFidesBolivia/) | mundo | Bolivia | es | 3 |
| `fb_record_news` | [Record News](https://www.facebook.com/recordnews/) | mundo | América Latina | pt | 3 |
| `fb_reduno` | [Red Uno de Bolivia](https://www.facebook.com/RedUnotv/) | mundo | Bolivia | es | 3 |
| `fb_reuters` | [Reuters](https://www.facebook.com/Reuters/) | mundo | Global | en | 5 |
| `fb_revista_semana` | [Revista Semana](https://www.facebook.com/RevistaSemana/) | mundo | América Latina | es | 3 |
| `fb_rtp_bolivia` | [RTP Bolivia](https://www.facebook.com/rtpbolivia/) | mundo | Bolivia | es | 3 |
| `fb_sky_news` | [Sky News](https://www.facebook.com/skynews/) | mundo | Europa | en | 4 |
| `fb_techcrunch` | [TechCrunch](https://www.facebook.com/techcrunch/) | tecnologia | Global | en | 3 |
| `fb_telemundo` | [Noticias Telemundo](https://www.facebook.com/noticiastelemundo/) | mundo | América del Norte | es | 3 |
| `fb_theverge` | [The Verge](https://www.facebook.com/verge/) | tecnologia | Global | en | 3 |
| `fb_tn_argentina` | [TN - Todo Noticias](https://www.facebook.com/todonoticias/) | mundo | América Latina | es | 4 |
| `fb_unitel` | [UNITEL Bolivia](https://www.facebook.com/unitelbolivia/) | mundo | Bolivia | es | 3 |
| `fb_univision` | [Univision Noticias](https://www.facebook.com/UnivisionNoticias/) | mundo | América del Norte | es | 3 |
| `fb_uol_noticias` | [UOL Notícias](https://www.facebook.com/UOLNoticias/) | mundo | América Latina | pt | 4 |
| `fb_urgente_bo` | [Urgente.bo](https://www.facebook.com/Urgente.boPeriodico/) | mundo | Bolivia | es | 3 |
| `fb_washington_post` | [The Washington Post](https://www.facebook.com/washingtonpost/) | mundo | América del Norte | en | 4 |
| `fb_who` | [World Health Organization](https://www.facebook.com/WHO/) | salud | Global | en | 4 |

## Medios globales en inglés

`config/fuentes/mundo_en.yaml` — 18 fuentes

| id | nombre | tema | región | idioma | peso |
|---|---|---|---|---|---|
| `rss_abc_au` | [ABC News Australia](https://www.abc.net.au/news/feed/51120/rss.xml) | mundo | Oceanía | en | 3 |
| `rss_africanews` | [Africanews](https://www.africanews.com/feed/rss) | mundo | África | en | 3 |
| `rss_aljazeera` | [Al Jazeera English](https://www.aljazeera.com/xml/rss/all.xml) | mundo | Medio Oriente | en | 4 |
| `rss_bbc_world` | [BBC News - World](https://feeds.bbci.co.uk/news/world/rss.xml) | mundo | Global | en | 5 |
| `rss_cbc_world` | [CBC News - World](https://www.cbc.ca/webfeed/rss/rss-world) | mundo | América del Norte | en | 3 |
| `rss_dw_en` | [Deutsche Welle - World](https://rss.dw.com/rdf/rss-en-world) | mundo | Europa | en | 4 |
| `rss_euronews` | [Euronews](https://www.euronews.com/rss?level=theme&name=news) | mundo | Europa | en | 3 |
| `rss_france24_en` | [France 24 - English](https://www.france24.com/en/rss) | mundo | Europa | en | 4 |
| `rss_guardian_world` | [The Guardian - World](https://www.theguardian.com/world/rss) | mundo | Global | en | 4 |
| `rss_independent_world` | [The Independent - World](https://www.independent.co.uk/news/world/rss) | mundo | Europa | en | 3 |
| `rss_jpost_intl` | [The Jerusalem Post - International](https://www.jpost.com/rss/rssfeedsinternational) | mundo | Medio Oriente | en | 3 |
| `rss_npr_world` | [NPR - World](https://feeds.npr.org/1004/rss.xml) | mundo | América del Norte | en | 3 |
| `rss_nyt_world` | [The New York Times - World](https://rss.nytimes.com/services/xml/rss/nyt/World.xml) | mundo | América del Norte | en | 4 |
| `rss_scmp` | [South China Morning Post](https://www.scmp.com/rss/91/feed) | mundo | Asia | en | 3 |
| `rss_sky_world` | [Sky News - World](https://feeds.skynews.com/feeds/rss/world.xml) | mundo | Europa | en | 3 |
| `rss_the_hindu_intl` | [The Hindu - International](https://www.thehindu.com/news/international/feeder/default.rss) | mundo | Asia | en | 3 |
| `rss_times_of_india` | [The Times of India - World](https://timesofindia.indiatimes.com/rssfeeds/296589292.cms) | mundo | Asia | en | 3 |
| `rss_wapo_world` | [The Washington Post - World](https://feeds.washingtonpost.com/rss/world) | mundo | América del Norte | en | 4 |

## Prensa en español

`config/fuentes/mundo_es.yaml` — 16 fuentes

| id | nombre | tema | región | idioma | peso |
|---|---|---|---|---|---|
| `rss_abc_es_internacional` | [ABC España - Internacional](https://www.abc.es/rss/2.0/internacional/) | mundo | Europa | es | 3 |
| `rss_bbc_mundo` | [BBC News Mundo](https://feeds.bbci.co.uk/mundo/rss.xml) | mundo | Global | es | 5 |
| `rss_clarin_mundo` | [Clarín - Mundo](https://www.clarin.com/rss/mundo/) | mundo | América Latina | es | 3 |
| `rss_cnn_espanol` | [CNN en Español](https://cnnespanol.cnn.com/feed/) | mundo | América Latina | es | 4 |
| `rss_dw_es` | [Deutsche Welle - Español](https://rss.dw.com/rdf/rss-es-all) | mundo | Europa | es | 4 |
| `rss_eldeber_bo` | [El Deber (Bolivia)](https://eldeber.com.bo/rss/) | mundo | Bolivia | es | 3 |
| `rss_elmundo_internacional` | [El Mundo - Internacional](https://e00-elmundo.uecdn.es/elmundo/rss/internacional.xml) | mundo | Europa | es | 3 |
| `rss_elpais_internacional` | [El País - Internacional](https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/internacional/portada) | mundo | Europa | es | 4 |
| `rss_eluniversal_mx` | [El Universal México](https://www.eluniversal.com.mx/rss.xml) | mundo | América Latina | es | 3 |
| `rss_erbol_bo` | [ERBOL (Bolivia)](https://erbol.com.bo/rss.xml) | mundo | Bolivia | es | 3 |
| `rss_france24_es` | [France 24 - Español](https://www.france24.com/es/rss) | mundo | Europa | es | 4 |
| `rss_infobae` | [Infobae](https://www.infobae.com/feeds/rss/) | mundo | América Latina | es | 3 |
| `rss_lanacion_mundo` | [La Nación - El Mundo](https://www.lanacion.com.ar/arc/outboundfeeds/rss/category/el-mundo/) | mundo | América Latina | es | 3 |
| `rss_lostiempos_bo` | [Los Tiempos (Bolivia)](https://www.lostiempos.com/rss.xml) | mundo | Bolivia | es | 3 |
| `rss_pagina12_mundo` | [Página/12 - El Mundo](https://www.pagina12.com.ar/rss/secciones/el-mundo/notas) | mundo | América Latina | es | 2 |
| `rss_rtve_internacional` | [RTVE - Internacional](https://api2.rtve.es/rss/temas_internacional.xml) | mundo | Europa | es | 3 |

## Fuentes por tema

`config/fuentes/temas.yaml` — 21 fuentes

| id | nombre | tema | región | idioma | peso |
|---|---|---|---|---|---|
| `rss_ars_technica` | [Ars Technica](https://feeds.arstechnica.com/arstechnica/index) | tecnologia | Global | en | 4 |
| `rss_bbc_business` | [BBC News - Business](https://feeds.bbci.co.uk/news/business/rss.xml) | economia | Global | en | 4 |
| `rss_bbc_sport` | [BBC Sport](https://feeds.bbci.co.uk/sport/rss.xml) | deportes | Global | en | 4 |
| `rss_cnbc_world` | [CNBC - World](https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100727362) | economia | Global | en | 4 |
| `rss_esa` | [European Space Agency](https://www.esa.int/rssfeed/Our_Activities/Space_News) | ciencia | Europa | en | 3 |
| `rss_espn` | [ESPN](https://www.espn.com/espn/rss/news) | deportes | Global | en | 3 |
| `rss_expansion` | [Expansión - Economía](https://e00-expansion.uecdn.es/rss/economia.xml) | economia | Europa | es | 3 |
| `rss_guardian_culture` | [The Guardian - Culture](https://www.theguardian.com/culture/rss) | cultura | Global | en | 3 |
| `rss_guardian_environment` | [The Guardian - Environment](https://www.theguardian.com/environment/rss) | ambiente | Global | en | 3 |
| `rss_hacker_news` | [Hacker News - Portada](https://hnrss.org/frontpage) | tecnologia | Global | en | 2 |
| `rss_marca` | [Marca](https://e00-marca.uecdn.es/rss/portada.xml) | deportes | Global | es | 3 |
| `rss_marketwatch` | [MarketWatch](https://feeds.content.dowjones.io/public/rss/mw_topstories) | economia | Global | en | 3 |
| `rss_mongabay` | [Mongabay](https://news.mongabay.com/feed/) | ambiente | Global | en | 3 |
| `rss_nasa` | [NASA](https://www.nasa.gov/news-release/feed/) | ciencia | Global | en | 4 |
| `rss_nature` | [Nature](https://www.nature.com/nature.rss) | ciencia | Global | en | 5 |
| `rss_phys_org` | [Phys.org](https://phys.org/rss-feed/) | ciencia | Global | en | 3 |
| `rss_science_daily` | [ScienceDaily](https://www.sciencedaily.com/rss/all.xml) | ciencia | Global | en | 3 |
| `rss_techcrunch` | [TechCrunch](https://techcrunch.com/feed/) | tecnologia | Global | en | 3 |
| `rss_the_verge` | [The Verge](https://www.theverge.com/rss/index.xml) | tecnologia | Global | en | 3 |
| `rss_variety` | [Variety](https://variety.com/feed/) | cultura | Global | en | 2 |
| `rss_xataka` | [Xataka](https://www.xataka.com/feedburner.xml) | tecnologia | Global | es | 3 |
