# Attribution for the edition maps

Maps agent, 2026-11-24.
Scope: the three static map images in replacements/ (p066-x251, p301-x1169, p302-x1173), the web map specs in site/figure-maps/, and the then-and-now layers in site/then-now.json.
Rule: each image carries only the minimum that each licence allows on the image. The full wording goes in the edition note that the EPUB prints under the image, and in the web credit.

## 1. OpenStreetMap (ODbL)

Source: OSMF, "Licence/Attribution Guidelines", https://osmfoundation.org/wiki/Licence/Attribution_Guidelines , revision 14786 of 2026-09-10. The raw text is saved in work/maps/sources/osm-attribution/page.wiki.

Exact clauses:

- "Attribution must be to “OpenStreetMap”."
- "Attribution must also make it clear that the data is available under the Open Database License. This may be done by making the text “OpenStreetMap” a link to openstreetmap.org/copyright, which has information about OpenStreetMap’s data sources (which OpenStreetMap needs to credit) as well as the ODbL."
- "The historical forms of attribution “© OpenStreetMap contributors” or “© OpenStreetMap” are acceptable."
- Safe harbour: "Attribution must be placed in the vicinity of the produced work or in a location where customarily attribution would be expected by the users of the produced work." and "Attribution must be legible and understandable."
- Static images: "Static images must be generally attributed the same way as interactive maps. However, if multiple static images appear on the same document, one instance of attribution is sufficient. (For images where hyperlinking is not possible, see the “Books, magazines and printed maps” section.)"
- Interactive maps: "While the lower right corner is traditional, any corner of the map is acceptable. Alternatively, the attribution may be placed adjacent to the map or on a splash screen or pop-up shown when a user starts the app, device, website, etc."
- Books, magazines, and printed maps: "For a printed map and similar media (that is ebooks, PDFs and so on), the credit must appear beside the map if that is where other such credits appear, or in a footnote/endnote if that is where other credits appear, or in the “acknowledgements” section of the publication (often at the start of a book or magazine) if that is where other credits appear. The URL to openstreetmap.org/copyright must be printed out."

What follows:

- In the EPUB, the credit may stand in the edition note under the image, because the edition puts its other image credits there. The note must print the URL openstreetmap.org/copyright.
- The licence does not require OSM text inside the image. The images still keep a small "© OpenStreetMap" in a corner, the shortest accepted form. The web reader can show an image without its caption (the figure dialog), and an image can travel on its own.
- Web maps (Leaflet): the credit sits in a map corner, with "OpenStreetMap" linked to https://www.openstreetmap.org/copyright.

## 2. Copernicus DEM (WorldDEM™-90 and WorldDEM-30)

Source: ESA, "Copernicus Contributing Mission Data Access" licence document, issue date 21/02/2025. It contains "Licence for COP-DEM-GLO-90-F Global 90m Full, Free & Open: Licence for the use of the Copernicus WorldDEM™-90" and the licence for the Copernicus WorldDEM-30: https://dataspace.copernicus.eu/sites/default/files/media/files/2025-06/copernicus_contributing_mission_data_access_v2_cop_dem_licenses.pdf . The WorldDEM-30 licence also stands alone: https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/DEM/resources/license/License-COPDEM-30.pdf . Both PDFs and their text are saved in work/maps/sources/copdem-licence/.

Exact clauses, Article 6 "User Obligations" of the WorldDEM™-90 licence. The WorldDEM-30 licence has the same text with "WorldDEM-30", without "™".

- (a) "When communicating to the General Public or distributing the Copernicus WorldDEM™-90, the User shall inform the General Public of the source by using the following notice: © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved."
- (b) "Where the Copernicus WorldDEM™-90 data have been adapted or modified, the User shall provide the following notice: "produced using Copernicus WorldDEM™-90 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved”."
- (c) "Users exercising the right of distribution or communication to the General Public of the Copernicus WorldDEM™-90, modified or not, must ensure that the Subsequent Users understand that neither the Licensor nor any other legal entities in charge of the Copernicus programme or the delivery of Copernicus data and information under the Copernicus programme may be held liable with regard to any aspect of the Copernicus WorldDEM™-90. The following sentence or its translation in any language shall be added by such Users in a licence or any legal warning or notice covering their distribution or communication to the General Public of the Copernicus WorldDEM™-90: "The organisations in charge of the Copernicus programme by law or by delegation do not incur any liability for any use of the Copernicus WorldDEM™-90"."
- (d) "User shall make sure not to convey the impression to the General Public that the user's activities are officially endorsed by the Provider, the Licensor or any other legal entities in charge of the Copernicus programme or the delivery of Copernicus data and information under the Copernicus programme."

What follows:

- The maps show relief computed from the DEM (hillshade and colour by height), so notice (b) applies, word for word. The licence fixes the wording but not its place. It does not ask for the notice inside the image.
- The notice therefore sits in the edition note under the image, in English as written. The image has no DEM text.
- The disclaimer of (c), in English or in a translation, belongs in the edition's legal or credits notice: the EPUB copyright or credits page, and the credits page of the web site. Suggested Hebrew translation: "הגופים האחראים לתוכנית קופרניקוס על פי דין או מכוח האצלה אינם נושאים באחריות כלשהי לשימוש כלשהו ב־Copernicus WorldDEM™-90 וב־Copernicus WorldDEM-30."
- p066 uses both products (90 m overview, 30 m detail panel) and carries both notices. p301 and p302 use WorldDEM™-90 only.

## 3. Natural Earth

Source: https://www.naturalearthdata.com/about/terms-of-use/ : "All versions of Natural Earth raster + vector map data found on this website are in the public domain." "No permission is needed to use Natural Earth." "Crediting the authors is unnecessary."
No credit in the image. The edition note names Natural Earth as a courtesy.

## 4. OpenTopoMap (web base map only)

Source: https://opentopomap.org/about , section "Verwendung": "Kartendaten: © OpenStreetMap-Mitwirkende, SRTM | Kartendarstellung: © OpenTopoMap (CC-BY-SA)". The page links "OpenStreetMap" to openstreetmap.org/copyright, "OpenTopoMap" to opentopomap.org, and "CC-BY-SA" to creativecommons.org/licenses/by-sa/3.0/.
The web map specs give the English form "Map data: © OpenStreetMap contributors, SRTM" and "Map display: © OpenTopoMap (CC-BY-SA)", with the three links in "attribution_links".

## 5. Copernicus Sentinel-2 (then-and-now layer)

Source: Sentinel data legal notice, https://sentinels.copernicus.eu/documents/247904/690755/Sentinel_Data_Legal_Notice : "Copernicus Sentinel data [Year]" for unmodified data, "Contains modified Copernicus Sentinel data [Year]" for modified data.
The layer image has no text. site/then-now.json gives the credit "Contains modified Copernicus Sentinel data 2026" for the web view to show with the layer.

## Resulting credit text

| Image | In the image | Full credit |
|---|---|---|
| p066-x251 | "© OpenStreetMap", lower left | Edition note: OSM with URL, Natural Earth, WorldDEM™-90 and WorldDEM-30 notices |
| p301-x1169 | "© OpenStreetMap", lower right | Edition note: OSM with URL, Natural Earth, WorldDEM™-90 notice |
| p302-x1173 | "© OpenStreetMap", lower left | Edition note: OSM with URL, WorldDEM™-90 notice |
| site/figure-maps/*.json | (web map corner) | "attribution" and "attribution_links" |
| then-now layers | none | "credit" of each layer |

The exact note text for book.toml is in work/maps/HANDOFF.md.
