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
          <section className="results-grid">
            <article className="panel">
              <h2>Accepted original</h2>
              <div className="document-preview" dangerouslySetInnerHTML={{ __html: state.result.originalHtml }} />
            </article>
            <article className="panel">
              <h2>Accepted revision</h2>
              <div className="document-preview" dangerouslySetInnerHTML={{ __html: state.result.revisedHtml }} />
            </article>
            <article className="panel">
              <h2>Diff output</h2>
              <div className="document-preview diff-html" dangerouslySetInnerHTML={{ __html: state.result.diffHtml }} />
            </article>
          </section>
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
