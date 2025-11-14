import { readFile } from 'fs/promises';
import JSZip from 'jszip';
import { DOMParser } from '@xmldom/xmldom';

const RELS_DIR = 'word/_rels/';
const PART_PREFIX = 'word/';

const NODE_TYPE = {
  ELEMENT: 1,
  TEXT: 3,
  CDATA_SECTION: 4
};

function toArray(nodeList) {
  const result = [];

  for (let index = 0; index < nodeList.length; index += 1) {
    result.push(nodeList.item(index));
  }

  return result;
}

function collectText(node) {
  if (!node) {
    return '';
  }

  if (node.nodeType === NODE_TYPE.TEXT || node.nodeType === NODE_TYPE.CDATA_SECTION) {
    return node.data || '';
  }

  if (node.nodeType !== NODE_TYPE.ELEMENT) {
    return '';
  }

  let result = '';
  for (let child = node.firstChild; child; child = child.nextSibling) {
    result += collectText(child);
  }

  return result;
}

function parseXml(content, fileName) {
  try {
    const parser = new DOMParser();
    const document = parser.parseFromString(content, 'application/xml');
    const errors = toArray(document.getElementsByTagName('parsererror'));

    if (errors.length > 0) {
      const message = collectText(errors[0]) || 'Unknown error';
      throw new Error(message.trim());
    }

    return document;
  } catch (error) {
    throw new Error(`Failed to parse XML in ${fileName}: ${error.message}`);
  }
}

function normalizeUrl(url) {
  return url == null ? '' : String(url);
}

function normalizeText(text) {
  return (text == null ? '' : String(text)).replace(/\s+/g, ' ').trim();
}

function extractHyperlinksFromDocument(document, part, relationshipMap) {
  const hyperlinks = [];
  const hyperlinkNodes = toArray(document.getElementsByTagName('w:hyperlink'));

  hyperlinkNodes.forEach((element) => {
    if (!element || element.nodeType !== NODE_TYPE.ELEMENT) {
      return;
    }

    const relId = element.getAttribute('r:id') || '';
    const url = relId && relationshipMap.has(relId)
      ? relationshipMap.get(relId)
      : null;
    const anchorText = normalizeText(collectText(element));

    hyperlinks.push({
      part,
      relId,
      url,
      anchorText
    });
  });

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
    const document = parseXml(xmlContent, relPath);
    const relationshipElements = toArray(document.getElementsByTagName('Relationship'));

    if (relationshipElements.length === 0) {
      continue;
    }

    const partRelationships = map.get(partName) || new Map();

    relationshipElements.forEach((element) => {
      if (!element || element.nodeType !== NODE_TYPE.ELEMENT) {
        return;
      }

      const type = element.getAttribute('Type');

      if (!type || !type.endsWith('/hyperlink')) {
        return;
      }

      const relId = element.getAttribute('Id');
      const target = element.getAttribute('Target') || null;

      if (!relId) {
        return;
      }

      partRelationships.set(relId, target);
    });

    if (partRelationships.size > 0) {
      map.set(partName, partRelationships);
    }
  }

  return map;
}

async function extractHyperlinks(filePath) {
  let buffer;

  try {
    buffer = await readFile(filePath);
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
    const document = parseXml(xmlContent, file.name);
    const relationships = relationshipMap.get(partName) || new Map();

    const partHyperlinks = extractHyperlinksFromDocument(document, partName, relationships);
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

export async function compareDocxHyperlinks(filePathA, filePathB) {
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
