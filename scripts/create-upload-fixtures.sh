#!/usr/bin/env bash
set -Eeuo pipefail

# Creates small, valid, non-sensitive files for the Sakai Resources UI test.
# The default directory is outside the repository so test binaries are never
# accidentally committed. Pass a different empty/test-only directory as $1.
DESTINATION="${1:-/tmp/sakai-upload-fixtures}"
mkdir -p "$DESTINATION"

printf '%s\n' '%PDF-1.4' '1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj' '2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj' '3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj' 'trailer<</Root 1 0 R>>' '%%EOF' > "$DESTINATION/sakai-upload-test.pdf"
printf '%s' 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9JQ8sAAAAASUVORK5CYII=' | openssl base64 -d -A > "$DESTINATION/sakai-upload-test.png"
printf '%s\n' 'Sakai resource upload verification fixture.' > "$DESTINATION/README.txt"
(cd "$DESTINATION" && rm -f sakai-upload-test.zip && zip -q sakai-upload-test.zip README.txt)

pptx_dir="$(mktemp -d)"
trap 'rm -rf "$pptx_dir"' EXIT
mkdir -p "$pptx_dir/_rels" "$pptx_dir/ppt/_rels"
printf '%s' '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/></Types>' > "$pptx_dir/[Content_Types].xml"
printf '%s' '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/></Relationships>' > "$pptx_dir/_rels/.rels"
printf '%s' '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:sldMasterIdLst/><p:sldIdLst/><p:sldSz cx="9144000" cy="6858000" type="screen4x3"/><p:notesSz cx="6858000" cy="9144000"/></p:presentation>' > "$pptx_dir/ppt/presentation.xml"
printf '%s' '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>' > "$pptx_dir/ppt/_rels/presentation.xml.rels"
(cd "$pptx_dir" && rm -f "$DESTINATION/sakai-upload-test.pptx" && zip -q -r "$DESTINATION/sakai-upload-test.pptx" .)

file "$DESTINATION"/sakai-upload-test.{pdf,png,zip,pptx}
echo "Fixtures ready in $DESTINATION"
