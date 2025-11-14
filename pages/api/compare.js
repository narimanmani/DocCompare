import formidable from 'formidable';
import HtmlDiffModule from 'htmldiff-js';
import { DOMParser } from '@xmldom/xmldom';
import { docxToAcceptedContent } from '../../lib/docx';
import { compareDocxHyperlinks } from '../../lib/compareDocxHyperlinks';

export const config = {
  api: {
    bodyParser: false
  }
};

function validateFile(file) {
  if (!file) {
    throw new Error('Missing file in upload.');
  }

  const allowedMime = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
  const extensionValid = file.originalFilename?.toLowerCase().endsWith('.docx');

  if (file.mimetype !== allowedMime && !extensionValid) {
    throw new Error('Only .docx files are supported.');
  }
}

function sanitizeHtml(html) {
  return html.replace(/\s{2,}/g, ' ').trim();
}

function escapeHtml(value) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function normalizePlainTextContent(text) {
  if (!text) {
    return '';
  }

  const normalized = text
    .replace(/\r\n/g, '\n')
    .split(/\n{2,}/)
    .map((paragraph) => paragraph.replace(/\s+/g, ' ').trim())
    .filter((paragraph) => paragraph.length > 0);

  if (normalized.length === 0) {
    return '';
  }

  return normalized
    .map((paragraph) => `<p>${escapeHtml(paragraph)}</p>`)
    .join('');
}

function buildHyperlinkChangeSummary(hyperlinkSummary) {
  if (!hyperlinkSummary) {
    return [];
  }

  const entries = [];
  let counter = 1;

  const pushEntry = ({ description, original, revised }) => {
    const part = original?.part || revised?.part || null;
    entries.push({
      id: `hyperlink-${counter}`,
      description,
      originalText: original?.anchorText ?? null,
      revisedText: revised?.anchorText ?? null,
      changeType: 'hyperlink',
      originalHref: original?.url ?? null,
      revisedHref: revised?.url ?? null,
      context: part ? `Part: ${part}` : null
    });
    counter += 1;
  };

  hyperlinkSummary.changedUrl?.forEach((change) => {
    pushEntry({
      description: 'Hyperlink URL updated',
      original: change.before,
      revised: change.after
    });
  });

  hyperlinkSummary.changedAnchorText?.forEach((change) => {
    pushEntry({
      description: 'Hyperlink text updated',
      original: change.before,
      revised: change.after
    });
  });

  hyperlinkSummary.added?.forEach((link) => {
    pushEntry({
      description: 'Hyperlink added in Doc 2',
      original: null,
      revised: link
    });
  });

  hyperlinkSummary.removed?.forEach((link) => {
    pushEntry({
      description: 'Hyperlink removed from Doc 1',
      original: link,
      revised: null
    });
  });

  return entries;
}

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    res.setHeader('Allow', ['POST']);
    res.status(405).send('Method Not Allowed');
    return;
  }

  const form = formidable({
    maxFileSize: 25 * 1024 * 1024,
    multiples: false,
    keepExtensions: false
  });

  try {
    const { files } = await new Promise((resolve, reject) => {
      form.parse(req, (error, fields, files) => {
        if (error) {
          reject(error);
          return;
        }

        req.files = files;
        resolve({ fields, files });
      });
    });

    const original = Array.isArray(files.docxA) ? files.docxA[0] : files.docxA;
    const revised = Array.isArray(files.docxB) ? files.docxB[0] : files.docxB;

    validateFile(original);
    validateFile(revised);

    const [originalBuffer, revisedBuffer] = await Promise.all([
      fsReadFile(original.filepath),
      fsReadFile(revised.filepath)
    ]);

    const [originalContent, revisedContent] = await Promise.all([
      docxToAcceptedContent(originalBuffer),
      docxToAcceptedContent(revisedBuffer)
    ]);

    const originalHtml = sanitizeHtml(originalContent.html);
    const revisedHtml = sanitizeHtml(revisedContent.html);

    const normalizedOriginal = normalizePlainTextContent(originalContent.text);
    const normalizedRevised = normalizePlainTextContent(revisedContent.text);

    const HtmlDiff = HtmlDiffModule?.default ?? HtmlDiffModule;
    const diffHtml = typeof HtmlDiff.execute === 'function'
      ? HtmlDiff.execute(normalizedOriginal, normalizedRevised)
      : new HtmlDiff(normalizedOriginal, normalizedRevised).build();

    const hyperlinkSummary = await compareDocxHyperlinks(original.filepath, revised.filepath);
    const textChanges = buildChangeSummary(diffHtml);
    const hyperlinkChanges = buildHyperlinkChangeSummary(hyperlinkSummary);
    const changes = [...textChanges, ...hyperlinkChanges];

    res.status(200).json({
      originalHtml,
      revisedHtml,
      diffHtml,
      changes,
      hyperlinkSummary
    });
  } catch (error) {
    console.error(error);
    res.status(400).send(error.message || 'Unable to compare documents.');
  } finally {
    await cleanupFiles([req?.files?.docxA, req?.files?.docxB]);
  }
}

async function fsReadFile(path) {
  const { readFile } = await import('fs/promises');
  return readFile(path);
}

async function fsUnlink(path) {
  const { unlink } = await import('fs/promises');
  try {
    await unlink(path);
  } catch (error) {
    if (error.code !== 'ENOENT') {
      console.warn('Unable to remove temp file', path, error);
    }
  }
}

function flattenFiles(files) {
  return files.flatMap((file) => (Array.isArray(file) ? file : file ? [file] : []));
}

async function cleanupFiles(files) {
  const removals = flattenFiles(files)
    .filter((file) => file?.filepath)
    .map((file) => fsUnlink(file.filepath));

  await Promise.all(removals);
}

function buildChangeSummary(diffHtml) {
  if (!diffHtml) {
    return [];
  }

  try {
    const parser = new DOMParser();
    const document = parser.parseFromString(`<body>${diffHtml}</body>`, 'text/html');
    const body = document?.documentElement;

    if (!body) {
      return [];
    }

    const deletions = Array.from(body.getElementsByTagName('del') || []);

    const changes = deletions
      .map((deletion, index) => summarizeChange(deletion, findMatchingInsertion(deletion), index))
      .filter(Boolean);

    return changes;
  } catch (error) {
    console.warn('Unable to build change summary', error);
    return [];
  }
}

function findMatchingInsertion(deletionNode) {
  if (!deletionNode) {
    return null;
  }

  let sibling = deletionNode.nextSibling;

  while (sibling) {
    if (sibling.nodeType === 1) {
      const tagName = sibling.nodeName?.toLowerCase();

      if (tagName === 'ins') {
        return sibling;
      }

      if (tagName === 'del') {
        break;
      }
    }

    sibling = sibling.nextSibling;
  }

  return null;
}

function summarizeChange(deletionNode, insertionNode, index) {
  if (!deletionNode && !insertionNode) {
    return null;
  }

  const originalText = normalizeText(deletionNode?.textContent || '');
  const revisedText = normalizeText(insertionNode?.textContent || '');
  const originalAnchor = findFirstAnchor(deletionNode);
  const revisedAnchor = findFirstAnchor(insertionNode);

  const changeType = originalAnchor || revisedAnchor ? 'hyperlink' : 'text';
  const originalHref = originalAnchor?.getAttribute('href') || null;
  const revisedHref = revisedAnchor?.getAttribute('href') || null;

  if (!originalText && !revisedText && !originalHref && !revisedHref) {
    return null;
  }

  const context = normalizeText(deletionNode?.parentNode?.textContent || '') || null;

  return {
    id: index + 1,
    description: changeType === 'hyperlink' ? 'Hyperlink updated' : 'Content updated',
    originalText: originalText || null,
    revisedText: revisedText || null,
    changeType,
    originalHref,
    revisedHref,
    context
  };
}

function findFirstAnchor(node) {
  if (!node) {
    return null;
  }

  const anchorInNode = findAnchorWithinNode(node);

  if (anchorInNode) {
    return anchorInNode;
  }

  return findAnchorInAncestors(node);
}

function findAnchorWithinNode(node) {
  if (!node) {
    return null;
  }

  if (node.nodeType === 1 && node.nodeName?.toLowerCase() === 'a') {
    return node;
  }

  if (!node.childNodes) {
    return null;
  }

  for (let i = 0; i < node.childNodes.length; i += 1) {
    const child = node.childNodes[i];
    const anchor = findAnchorWithinNode(child);

    if (anchor) {
      return anchor;
    }
  }

  return null;
}

function findAnchorInAncestors(node) {
  let current = node?.parentNode || null;

  while (current) {
    if (current.nodeType === 1 && current.nodeName?.toLowerCase() === 'a') {
      return current;
    }

    current = current.parentNode || null;
  }

  return null;
}

function normalizeText(text) {
  return text.replace(/\s+/g, ' ').trim();
}
