const fs = require('fs/promises');
const JSZip = require('jszip');
const { XMLParser } = require('fast-xml-parser');

const RELS_DIR = 'word/_rels/';
const PART_PREFIX = 'word/';

const XML_PARSER_OPTIONS = {
  ignoreAttributes: false,
  attributeNamePrefix: '@_',
  textNodeName: '#text'
};

function parseXml(content, fileName) {
  try {
    const parser = new XMLParser(XML_PARSER_OPTIONS);
    return parser.parse(content);
  } catch (error) {
    throw new Error(`Failed to parse XML in ${fileName}: ${error.message}`);
  }
}

function normalizeUrl(url) {
  return url == null ? '' : String(url);
}

function normalizeText(text) {
  return (text || '').trim();
}

function collectText(value) {
  if (value == null) {
    return '';
  }

  if (typeof value === 'string') {
    return value;
  }

  if (Array.isArray(value)) {
    return value.map(collectText).join('');
  }

  if (typeof value === 'object') {
    let result = '';

    if (value['#text']) {
      result += value['#text'];
    }

    for (const [key, child] of Object.entries(value)) {
      if (key === '#text' || key.startsWith('@_')) {
        continue;
      }

      if (key === 'w:t') {
        result += collectText(child);
      } else {
        result += collectText(child);
      }
    }

    return result;
  }

  return '';
}

function extractHyperlinksFromNode(node, part, relationshipMap) {
  const hyperlinks = [];

  function traverse(current) {
    if (current == null) {
      return;
    }

    if (Array.isArray(current)) {
      current.forEach(traverse);
      return;
    }

    if (typeof current !== 'object') {
      return;
    }

    for (const [key, value] of Object.entries(current)) {
      if (key === 'w:hyperlink') {
        const hyperlinkNodes = Array.isArray(value) ? value : [value];

        hyperlinkNodes.forEach((hyperlinkNode) => {
          if (hyperlinkNode == null || typeof hyperlinkNode !== 'object') {
            return;
          }

          const relId = hyperlinkNode['@_r:id'] || null;
          const url = relId && relationshipMap.has(relId)
            ? relationshipMap.get(relId)
            : null;
          const anchorText = collectText(hyperlinkNode);

          hyperlinks.push({
            part,
            relId: relId || '',
            url,
            anchorText
          });
        });
      } else if (!key.startsWith('@_')) {
        traverse(value);
      }
    }
  }

  traverse(node);

  return hyperlinks;
}

async function buildRelationshipMap(zip) {
  const relationshipFiles = zip.file(/^word\/_rels\/.*\.rels$/);
  const map = new Map();

  for (const file of relationshipFiles) {
    const relPath = file.name;
    const partName = relPath
      .replace(RELS_DIR, '')
      .replace(/\.rels$/i, '');

    const xmlContent = await file.async('string');
    const xml = parseXml(xmlContent, relPath);

    const relationships = xml.Relationships && xml.Relationships.Relationship;
    if (!relationships) {
      continue;
    }

    const relationshipArray = Array.isArray(relationships)
      ? relationships
      : [relationships];

    for (const relationship of relationshipArray) {
      const type = relationship['@_Type'];

      if (!type || !type.endsWith('/hyperlink')) {
        continue;
      }

      const relId = relationship['@_Id'];
      const target = relationship['@_Target'] || null;

      if (!relId) {
        continue;
      }

      if (!map.has(partName)) {
        map.set(partName, new Map());
      }

      map.get(partName).set(relId, target);
    }
  }

  return map;
}

async function extractHyperlinks(filePath) {
  let buffer;

  try {
    buffer = await fs.readFile(filePath);
  } catch (error) {
    throw new Error(`Failed to read file at ${filePath}: ${error.message}`);
  }

  let zip;

  try {
    zip = await JSZip.loadAsync(buffer);
  } catch (error) {
    throw new Error(`Failed to open DOCX file at ${filePath}: ${error.message}`);
  }

  const relationshipMap = await buildRelationshipMap(zip);

  const documentFile = zip.file('word/document.xml');
  if (!documentFile) {
    throw new Error('word/document.xml not found in DOCX');
  }

  const partFiles = new Map();

  partFiles.set('document.xml', documentFile);

  zip
    .file(/^word\/(header\d+|footer\d+)\.xml$/)
    .forEach((file) => {
      const partName = file.name.replace(PART_PREFIX, '');
      partFiles.set(partName, file);
    });

  for (const partName of relationshipMap.keys()) {
    if (!partFiles.has(partName)) {
      const relatedFile = zip.file(`${PART_PREFIX}${partName}`);

      if (!relatedFile) {
        throw new Error(`${PART_PREFIX}${partName} not found in DOCX`);
      }

      partFiles.set(partName, relatedFile);
    }
  }

  const hyperlinks = [];

  for (const [partName, file] of partFiles.entries()) {
    const xmlContent = await file.async('string');
    const xml = parseXml(xmlContent, file.name);
    const relationships = relationshipMap.get(partName) || new Map();

    const partHyperlinks = extractHyperlinksFromNode(xml, partName, relationships);
    hyperlinks.push(...partHyperlinks);
  }

  return hyperlinks;
}

function buildMap(links, keyFn) {
  const map = new Map();

  for (const link of links) {
    const key = keyFn(link);
    if (!map.has(key)) {
      map.set(key, []);
    }

    map.get(key).push(link);
  }

  return map;
}

function compareByPartAndAnchor(linksA, linksB, accountedA, accountedB, changedUrl) {
  const mapA = buildMap(linksA, (link) => `${link.part}||${normalizeText(link.anchorText)}`);
  const mapB = buildMap(linksB, (link) => `${link.part}||${normalizeText(link.anchorText)}`);

  const allKeys = new Set([...mapA.keys(), ...mapB.keys()]);

  for (const key of allKeys) {
    const arrA = mapA.get(key) || [];
    const arrB = mapB.get(key) || [];

    const usedB = new Array(arrB.length).fill(false);
    const matchedA = new Set();

    // First try to match hyperlinks where the URL stayed the same
    for (let indexA = 0; indexA < arrA.length; indexA += 1) {
      const linkA = arrA[indexA];
      const matchIndex = arrB.findIndex(
        (linkB, indexB) =>
          !usedB[indexB] && normalizeUrl(linkA.url) === normalizeUrl(linkB.url)
      );

      if (matchIndex !== -1) {
        usedB[matchIndex] = true;
        matchedA.add(indexA);
        accountedA.add(linkA);
        accountedB.add(arrB[matchIndex]);
      }
    }

    // Any remaining matches mean the URL changed
    for (let indexA = 0; indexA < arrA.length; indexA += 1) {
      if (matchedA.has(indexA)) {
        continue;
      }

      const linkA = arrA[indexA];
      const matchIndex = arrB.findIndex((_, indexB) => !usedB[indexB]);

      if (matchIndex !== -1) {
        const linkB = arrB[matchIndex];
        usedB[matchIndex] = true;
        matchedA.add(indexA);
        changedUrl.push({ before: linkA, after: linkB });
        accountedA.add(linkA);
        accountedB.add(linkB);
      }
    }
  }
}

function compareByPartAndUrl(linksA, linksB, accountedA, accountedB, changedAnchorText) {
  const mapA = buildMap(linksA, (link) => `${link.part}||${normalizeUrl(link.url)}`);
  const mapB = buildMap(linksB, (link) => `${link.part}||${normalizeUrl(link.url)}`);

  const allKeys = new Set([...mapA.keys(), ...mapB.keys()]);

  for (const key of allKeys) {
    const arrA = mapA.get(key) || [];
    const arrB = mapB.get(key) || [];

    const usedB = new Array(arrB.length).fill(false);
    const matchedA = new Set();

    // Match identical anchor text first
    for (let indexA = 0; indexA < arrA.length; indexA += 1) {
      const linkA = arrA[indexA];
      const matchIndex = arrB.findIndex(
        (linkB, indexB) =>
          !usedB[indexB] && normalizeText(linkA.anchorText) === normalizeText(linkB.anchorText)
      );

      if (matchIndex !== -1) {
        usedB[matchIndex] = true;
        matchedA.add(indexA);
        accountedA.add(linkA);
        accountedB.add(arrB[matchIndex]);
      }
    }

    const remainingA = [];
    const remainingB = [];

    for (let indexA = 0; indexA < arrA.length; indexA += 1) {
      if (!matchedA.has(indexA)) {
        remainingA.push(arrA[indexA]);
      }
    }

    for (let indexB = 0; indexB < arrB.length; indexB += 1) {
      if (!usedB[indexB]) {
        remainingB.push(arrB[indexB]);
      }
    }

    const pairCount = Math.min(remainingA.length, remainingB.length);

    for (let index = 0; index < pairCount; index += 1) {
      const linkA = remainingA[index];
      const linkB = remainingB[index];

      changedAnchorText.push({ before: linkA, after: linkB });
      accountedA.add(linkA);
      accountedB.add(linkB);
    }
  }
}

async function compareDocxHyperlinks(filePathA, filePathB) {
  const [linksA, linksB] = await Promise.all([
    extractHyperlinks(filePathA),
    extractHyperlinks(filePathB)
  ]);

  const accountedA = new Set();
  const accountedB = new Set();
  const changedUrl = [];
  const changedAnchorText = [];

  compareByPartAndAnchor(linksA, linksB, accountedA, accountedB, changedUrl);

  const remainingA = linksA.filter((link) => !accountedA.has(link));
  const remainingB = linksB.filter((link) => !accountedB.has(link));

  compareByPartAndUrl(remainingA, remainingB, accountedA, accountedB, changedAnchorText);

  const added = linksB.filter((link) => !accountedB.has(link));
  const removed = linksA.filter((link) => !accountedA.has(link));

  return {
    added,
    removed,
    changedUrl,
    changedAnchorText
  };
}

module.exports = {
  extractHyperlinks,
  compareDocxHyperlinks
};
