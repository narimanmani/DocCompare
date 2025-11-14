import JSZip from 'jszip';
import { DOMParser, XMLSerializer } from '@xmldom/xmldom';
import mammoth from 'mammoth';

const TRACKED_CHANGE_XML = [
  'word/document.xml',
  'word/footnotes.xml',
  'word/endnotes.xml'
];

function removeNodes(nodeList) {
  Array.from(nodeList).forEach((node) => {
    if (node.parentNode) {
      node.parentNode.removeChild(node);
    }
  });
}

function unwrapNodes(nodeList) {
  Array.from(nodeList).forEach((node) => {
    if (!node.parentNode) {
      return;
    }

    while (node.firstChild) {
      node.parentNode.insertBefore(node.firstChild, node);
    }

    node.parentNode.removeChild(node);
  });
}

async function acceptTrackedChanges(buffer) {
  const zip = await JSZip.loadAsync(buffer);

  const trackedFiles = new Set(
    zip
      .file(/^word\/(document|footnotes|endnotes|header\d+|footer\d+)\.xml$/)
      .map((file) => file.name)
  );

  TRACKED_CHANGE_XML.forEach((file) => trackedFiles.add(file));

  if (!trackedFiles.has('word/document.xml')) {
    throw new Error('The uploaded file is not a valid .docx document.');
  }

  for (const fileName of trackedFiles) {
    const file = zip.file(fileName);

    if (!file) {
      continue;
    }

    const xmlString = await file.async('string');
    const dom = new DOMParser().parseFromString(xmlString, 'application/xml');

    removeNodes(dom.getElementsByTagName('w:del'));
    removeNodes(dom.getElementsByTagName('w:delText'));
    removeNodes(dom.getElementsByTagName('w:commentRangeStart'));
    removeNodes(dom.getElementsByTagName('w:commentRangeEnd'));
    removeNodes(dom.getElementsByTagName('w:bookmarkStart'));
    removeNodes(dom.getElementsByTagName('w:bookmarkEnd'));
    removeNodes(dom.getElementsByTagName('w:proofErr'));

    unwrapNodes(dom.getElementsByTagName('w:ins'));
    unwrapNodes(dom.getElementsByTagName('w:moveTo'));
    unwrapNodes(dom.getElementsByTagName('w:moveToRangeStart'));
    unwrapNodes(dom.getElementsByTagName('w:moveToRangeEnd'));

    removeNodes(dom.getElementsByTagName('w:trackChange'));
    removeNodes(dom.getElementsByTagName('w:moveFrom'));
    removeNodes(dom.getElementsByTagName('w:moveFromRangeStart'));
    removeNodes(dom.getElementsByTagName('w:moveFromRangeEnd'));

    const cleanedXml = new XMLSerializer().serializeToString(dom);
    zip.file(fileName, cleanedXml);
  }

  return zip.generateAsync({ type: 'nodebuffer' });
}

export async function docxToAcceptedContent(buffer) {
  const cleanBuffer = await acceptTrackedChanges(buffer);

  const [htmlResult, textResult] = await Promise.all([
    mammoth.convertToHtml({ buffer: cleanBuffer }, {
      includeDefaultStyleMap: true,
      convertImage: mammoth.images.inline(async () => null)
    }),
    mammoth.extractRawText({ buffer: cleanBuffer })
  ]);

  return {
    html: htmlResult?.value ?? '',
    text: textResult?.value ?? ''
  };
}

export async function docxToAcceptedHtml(buffer) {
  const { html } = await docxToAcceptedContent(buffer);
  return html;
}
