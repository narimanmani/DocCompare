import formidable from 'formidable';
import HtmlDiffModule from 'htmldiff-js';
import { DOMParser } from '@xmldom/xmldom';
import { docxToAcceptedHtml } from '../../lib/docx';

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

    const [originalHtml, revisedHtml] = await Promise.all([
      docxToAcceptedHtml(originalBuffer),
      docxToAcceptedHtml(revisedBuffer)
    ]);

    const cleanOriginal = sanitizeHtml(originalHtml);
    const cleanRevised = sanitizeHtml(revisedHtml);

    const HtmlDiff = HtmlDiffModule?.default ?? HtmlDiffModule;
    const diffHtml = typeof HtmlDiff.execute === 'function'
      ? HtmlDiff.execute(cleanOriginal, cleanRevised)
      : new HtmlDiff(cleanOriginal, cleanRevised).build();

    const changes = buildChangeSummary(diffHtml);

    res.status(200).json({
      originalHtml: cleanOriginal,
      revisedHtml: cleanRevised,
      diffHtml,
      changes
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
