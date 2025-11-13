#!/usr/bin/env node

const { compareDocxHyperlinks } = require('./index');

function formatLink(link) {
  const anchor = link.anchorText ? `"${link.anchorText}"` : '""';
  const url = link.url ? link.url : 'null';
  return `[${link.part}] ${anchor} -> ${url}`;
}

function printList(title, links) {
  console.log(`${title}:`);
  if (links.length === 0) {
    console.log('- None');
    return;
  }

  links.forEach((link) => {
    console.log(`- ${formatLink(link)}`);
  });
}

function printChanges(title, changes, formatter) {
  console.log(`${title}:`);
  if (changes.length === 0) {
    console.log('- None');
    return;
  }

  changes.forEach((change) => {
    console.log(`- ${formatter(change)}`);
  });
}

async function main() {
  const [fileA, fileB] = process.argv.slice(2);

  if (!fileA || !fileB) {
    console.error('Usage: node demo.js <docA.docx> <docB.docx>');
    process.exit(1);
  }

  try {
    const diff = await compareDocxHyperlinks(fileA, fileB);

    printList('Added links', diff.added);
    console.log('');

    printList('Removed links', diff.removed);
    console.log('');

    printChanges('Links with changed URL', diff.changedUrl, ({ before, after }) => {
      const anchor = before.anchorText ? `"${before.anchorText}"` : '""';
      const beforeUrl = before.url ? before.url : 'null';
      const afterUrl = after.url ? after.url : 'null';
      return `[${before.part}] ${anchor} : ${beforeUrl} -> ${afterUrl}`;
    });
    console.log('');

    printChanges('Links with changed anchor text', diff.changedAnchorText, ({ before, after }) => {
      const url = before.url || after.url || 'null';
      const beforeText = before.anchorText ? `"${before.anchorText}"` : '""';
      const afterText = after.anchorText ? `"${after.anchorText}"` : '""';
      return `[${before.part}] ${url} : ${beforeText} -> ${afterText}`;
    });
  } catch (error) {
    console.error(`Error comparing documents: ${error.message}`);
    process.exit(1);
  }
}

main();
