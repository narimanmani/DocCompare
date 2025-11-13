import { useCallback, useState } from 'react';

const initialState = {
  isComparing: false,
  error: null,
  result: null
};

export default function Home() {
  const [state, setState] = useState(initialState);

  const onSubmit = useCallback(async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const { docxA, docxB } = form;

    if (!docxA.files.length || !docxB.files.length) {
      setState((prev) => ({ ...prev, error: 'Please select both documents before running a comparison.' }));
      return;
    }

    const formData = new FormData();
    formData.append('docxA', docxA.files[0]);
    formData.append('docxB', docxB.files[0]);

    setState({ isComparing: true, error: null, result: null });

    try {
      const response = await fetch('/api/compare', {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        const message = await response.text();
        throw new Error(message || 'Comparison failed. Please try again.');
      }

      const data = await response.json();
      setState({ isComparing: false, error: null, result: data });
    } catch (error) {
      console.error(error);
      setState({ isComparing: false, error: error.message, result: null });
    }
  }, []);

  const renderLinkDetails = (label, link) => (
    <div className="hyperlink-change__column">
      <div className="hyperlink-change__column-label">{label}</div>
      {link ? (
        <>
          <div className="hyperlink-change__text">
            <span className="hyperlink-change__text-label">Anchor text:</span>{' '}
            {link.anchorText ? (
              <span>{link.anchorText}</span>
            ) : (
              <span className="hyperlink-change__empty">No anchor text</span>
            )}
          </div>
          <div className="hyperlink-change__text">
            <span className="hyperlink-change__text-label">URL:</span>{' '}
            {link.url ? (
              <a href={link.url} target="_blank" rel="noreferrer" className="hyperlink-change__url">
                {link.url}
              </a>
            ) : (
              <span className="hyperlink-change__empty">No URL</span>
            )}
          </div>
          {link.part && (
            <div className="hyperlink-change__meta">Location: {link.part}</div>
          )}
        </>
      ) : (
        <div className="hyperlink-change__empty">Not present</div>
      )}
    </div>
  );

  const renderHyperlinkEntry = (typeLabel, before, after, key, badgeModifier = '') => (
    <div className="hyperlink-change" key={key}>
      <div className={`hyperlink-change__badge ${badgeModifier}`.trim()}>{typeLabel}</div>
      <div className="hyperlink-change__columns">
        {renderLinkDetails('Doc 1', before)}
        {renderLinkDetails('Doc 2', after)}
      </div>
    </div>
  );

  const hyperlinkSummary = state.result?.hyperlinkSummary || {};
  const { added = [], removed = [], changedUrl = [], changedAnchorText = [] } = hyperlinkSummary;
  const hasHyperlinkChanges = added.length + removed.length + changedUrl.length + changedAnchorText.length > 0;

  return (
    <main>
      <div className="container">
        <header>
          <h1>DocCompare</h1>
          <p>Upload two Word documents (.docx) to review an HTML diff with tracked changes accepted automatically.</p>
        </header>

        <form onSubmit={onSubmit}>
          <div>
            <label htmlFor="docxA">Original document (.docx)</label>
            <input id="docxA" name="docxA" type="file" accept=".docx" />
          </div>

          <div>
            <label htmlFor="docxB">Revised document (.docx)</label>
            <input id="docxB" name="docxB" type="file" accept=".docx" />
          </div>

          <button type="submit" disabled={state.isComparing}>
            {state.isComparing ? 'Comparing…' : 'Compare documents'}
          </button>

          {state.error && <div className="error">{state.error}</div>}
        </form>

        {state.result && (
          <>
            <section className="results-grid">
              <article className="panel panel--changes panel--full">
                <h2>Change summary</h2>
                {state.result.changes && state.result.changes.length > 0 ? (
                  <div className="table-wrapper">
                  <table className="changes-table">
                    <thead>
                      <tr>
                        <th scope="col">Change</th>
                        <th scope="col">Doc 1 value</th>
                        <th scope="col">Doc 2 value</th>
                      </tr>
                    </thead>
                    <tbody>
                      {state.result.changes.map((change) => (
                        <tr key={change.id}>
                          <td>
                            <div className="change-summary">
                              <span className={`change-pill change-pill--${change.changeType}`}>
                                {change.changeType === 'hyperlink' ? 'Hyperlink' : 'Text'}
                              </span>
                              <div className="change-description">{change.description}</div>
                              {change.context && (
                                <div className="change-context">{change.context}</div>
                              )}
                            </div>
                          </td>
                          <td>
                            <div className="change-value">
                              {change.originalText ?? '—'}
                            </div>
                            {change.originalHref && (
                              <div className="change-href">
                                <span>Link:</span>{' '}
                                <a href={change.originalHref} target="_blank" rel="noreferrer">
                                  {change.originalHref}
                                </a>
                              </div>
                            )}
                          </td>
                          <td>
                            <div className="change-value">
                              {change.revisedText ?? '—'}
                            </div>
                            {change.revisedHref && (
                              <div className="change-href">
                                <span>Link:</span>{' '}
                                <a href={change.revisedHref} target="_blank" rel="noreferrer">
                                  {change.revisedHref}
                                </a>
                              </div>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                ) : (
                  <p className="no-changes">No changes detected between the documents.</p>
                )}
              </article>

              <article className="panel panel--full">
                <h2>Hyperlink comparison</h2>
                {hasHyperlinkChanges ? (
                  <div className="hyperlink-groups">
                    {changedUrl.length > 0 && (
                      <section>
                        <h3>Links with updated URLs</h3>
                        <div className="hyperlink-change-list">
                          {changedUrl.map((entry, index) =>
                            renderHyperlinkEntry(
                              'Updated URL',
                              entry.before,
                              entry.after,
                              `changed-url-${index}`,
                              'hyperlink-change__badge--updated'
                            )
                          )}
                        </div>
                      </section>
                    )}

                    {changedAnchorText.length > 0 && (
                      <section>
                        <h3>Links with updated anchor text</h3>
                        <div className="hyperlink-change-list">
                          {changedAnchorText.map((entry, index) =>
                            renderHyperlinkEntry(
                              'Updated text',
                              entry.before,
                              entry.after,
                              `changed-anchor-${index}`,
                              'hyperlink-change__badge--updated'
                            )
                          )}
                        </div>
                      </section>
                    )}

                    {added.length > 0 && (
                      <section>
                        <h3>Links added in Doc 2</h3>
                        <div className="hyperlink-change-list">
                          {added.map((entry, index) =>
                            renderHyperlinkEntry(
                              'Added hyperlink',
                              null,
                              entry,
                              `added-${index}`,
                              'hyperlink-change__badge--added'
                            )
                          )}
                        </div>
                      </section>
                    )}

                    {removed.length > 0 && (
                      <section>
                        <h3>Links removed from Doc 1</h3>
                        <div className="hyperlink-change-list">
                          {removed.map((entry, index) =>
                            renderHyperlinkEntry(
                              'Removed hyperlink',
                              entry,
                              null,
                              `removed-${index}`,
                              'hyperlink-change__badge--removed'
                            )
                          )}
                        </div>
                      </section>
                    )}
                  </div>
                ) : (
                  <p className="no-changes">No hyperlink differences detected.</p>
                )}
              </article>

              <article className="panel">
                <h2>Accepted original</h2>
                <div className="document-preview" dangerouslySetInnerHTML={{ __html: state.result.originalHtml }} />
              </article>
              <article className="panel">
                <h2>Accepted revision</h2>
                <div className="document-preview" dangerouslySetInnerHTML={{ __html: state.result.revisedHtml }} />
              </article>
            </section>

            <section className="diff-section">
              <article className="panel panel--diff">
                <h2>Diff output</h2>
                <div className="document-preview diff-html" dangerouslySetInnerHTML={{ __html: state.result.diffHtml }} />
              </article>
            </section>
          </>
        )}

        <aside className="instructions">
          <h2>How comparisons work</h2>
          <ul>
            <li>Tracked changes in both uploads are accepted automatically before processing.</li>
            <li>Documents are converted to HTML with hyperlinks preserved.</li>
            <li>The diff combines <code>htmldiff-js</code> with the accepted HTML to highlight insertions and deletions.</li>
          </ul>
        </aside>
      </div>
    </main>
  );
}
