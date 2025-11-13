import formidable from 'formidable';
import HtmlDiffModule from 'htmldiff-js';
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

    res.status(200).json({
      originalHtml: cleanOriginal,
      revisedHtml: cleanRevised,
      diffHtml
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
