/**
 * Blog Studio — bulk PDF and URL intake for the Conversations blog.
 *
 * WHAT THIS PAGE DOES, AND WHY IT DOES NOT UPLOAD.
 *
 * The operator drops PDFs and pastes URLs, picks one of the two categories, and exports a
 * WORK ORDER. `scripts/blog_ingest.py --work-order <file>` then does the extraction, the
 * ledger registration and the quality gate.
 *
 * It would be easy to make this page POST the files somewhere and call it an upload, and
 * it would be worse. Three reasons, in order of weight:
 *
 *   1. The public site is a static export (`output: 'export'`), and there is no ingest
 *      backend for blog sources today. A button that appeared to upload and silently did
 *      nothing is the worst available outcome.
 *   2. Thousands of sources is the stated requirement. API Gateway cuts a Lambda
 *      integration off at 30 seconds and Lambda itself at 15 minutes; the path that has
 *      actually delivered 340 articles in this repo is a local script plus a committed
 *      manifest. Routing bulk work through a browser would be slower and less resumable.
 *   3. Extraction and the quality standard must exist in exactly ONE implementation. A
 *      browser copy of the section 13 phrase list would drift from the Python one, and
 *      two gates that disagree is worse than one gate.
 *
 * What the browser genuinely contributes is the SHA-256. It is computed here over the
 * selected bytes with WebCrypto, and `read_work_order` re-checks it against the file it
 * finds on disk. A mismatch means the operator picked a different file than intended, and
 * catching it there is the difference between a caught mistake and permanently wrong
 * provenance on a published article.
 */
import React, { useCallback, useMemo, useRef, useState } from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';

interface PageProps { signOut?: () => void; user?: any; }

/**
 * The two categories, and the two article classes.
 *
 * Mirrors `CATEGORIES` and `ARTICLE_CLASSES` in scripts/blog_quality_v2.py, which is the
 * authority. `src/test/BlogStudioCategories.test.ts` reads that file and fails if the two
 * lists drift, because a category this page can emit but the gate rejects would produce a
 * work order that dies at ingestion.
 *
 * A fixed list rather than a free-text datalist is deliberate. The older Blog Creator
 * form uses `<input list=...>`, so a typo silently creates a third category — and
 * `/blog/` serves whichever category sorts FIRST alphabetically, which means
 * "Conversatons" would have taken over the public blog index.
 */
const CATEGORIES = [ 'Conversations', 'Gastronomy' ] as const;
const ARTICLE_CLASSES = [ 'ARCHIVE_DERIVED', 'ORIGINAL_109' ] as const;

type Category = typeof CATEGORIES[ number ];
type ArticleClass = typeof ARTICLE_CLASSES[ number ];

/** Section 29, split by who can decide it. Kept in step with blog_quality_v2.HUMAN_GATES. */
const MACHINE_GATES = [ 'NON_DUPLICATION', 'TIGHTNESS', 'METADATA' ] as const;
const HUMAN_GATES = [
  'DISTINCTION', 'SOURCE_FIDELITY', 'CLARITY', 'VALUE', 'ORIGINAL_EXPRESSION',
  'SUBSTANCE', 'VOICE', 'FACTUAL_INTEGRITY', 'ATTRIBUTION', 'PRIVACY',
  'HUMAN_QUALITY_TEST',
] as const;

interface PickedFile {
  name: string;
  size: number;
  sha256: string;
  /** Per-file overrides, so one order can mix both categories. */
  category: Category;
  articleClass: ArticleClass;
}

interface LedgerRow {
  sourceType: string;
  sourceRef: string;
  sourceSha256: string;
  status: string;
  category: string;
  slug: string;
  title: string;
  sourceTitle: string;
  extractedWords: number;
  batchFile: string;
  publishedAt: string;
  error: string;
}

interface StudioProps extends PageProps {
  ledger: LedgerRow[];
  ledgerUpdatedAt: string;
  ledgerPresent: boolean;
}

type Tab = 'intake' | 'ledger' | 'standard';

const th: React.CSSProperties = {
  padding: '8px 10px', textAlign: 'left', fontSize: 11, fontWeight: 600, color: '#6b7280',
  borderBottom: '1px solid #e5e7eb',
};
const td: React.CSSProperties = { padding: '6px 10px', fontSize: 12, verticalAlign: 'top' };
const btn: React.CSSProperties = {
  padding: '6px 14px', borderRadius: 6, border: 'none', cursor: 'pointer', fontSize: 12,
  fontFamily: 'inherit',
};
const label: React.CSSProperties = {
  fontSize: 12, fontWeight: 600, color: '#374151', display: 'block', marginBottom: 4,
};
const input: React.CSSProperties = {
  width: '100%', padding: '8px 12px', borderRadius: 8, border: '1.5px solid #e5e7eb',
  fontSize: 13, fontFamily: 'inherit',
};

/** SHA-256 of the selected bytes, matching what Python computes over the same file. */
async function sha256 ( file: File ): Promise<string> {
  const buffer = await file.arrayBuffer();
  const digest = await crypto.subtle.digest( 'SHA-256', buffer );
  return Array.from( new Uint8Array( digest ) )
    .map( ( byte ) => byte.toString( 16 ).padStart( 2, '0' ) )
    .join( '' );
}

function formatBytes ( size: number ): string {
  if ( size < 1024 ) return `${ size } B`;
  if ( size < 1024 * 1024 ) return `${ ( size / 1024 ).toFixed( 0 ) } kB`;
  return `${ ( size / ( 1024 * 1024 ) ).toFixed( 1 ) } MB`;
}

/**
 * URLs, one per line, `#` comments dropped — the same shape `--url-file` accepts, so the
 * same text can be pasted here or saved as a file without transformation.
 */
function parseUrls ( raw: string ): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for ( const line of raw.split( /\r?\n/ ) )
  {
    const trimmed = line.trim();
    if ( !trimmed || trimmed.startsWith( '#' ) ) continue;
    const value = /^https?:\/\//i.test( trimmed ) ? trimmed : `https://${ trimmed }`;
    if ( seen.has( value ) ) continue;
    seen.add( value );
    out.push( value );
  }
  return out;
}

const BlogStudio: React.FC<StudioProps> = ( { signOut, user, ledger, ledgerUpdatedAt, ledgerPresent } ) => {
  const [ tab, setTab ] = useState<Tab>( 'intake' );
  const [ files, setFiles ] = useState<PickedFile[]>( [] );
  const [ urlText, setUrlText ] = useState( '' );
  const [ category, setCategory ] = useState<Category>( 'Conversations' );
  const [ articleClass, setArticleClass ] = useState<ArticleClass>( 'ARCHIVE_DERIVED' );
  const [ hashing, setHashing ] = useState( false );
  const [ log, setLog ] = useState<string[]>( [] );
  const [ dragging, setDragging ] = useState( false );
  const fileInput = useRef<HTMLInputElement>( null );

  const addLog = useCallback( ( message: string ) => {
    setLog( ( previous ) => [ ...previous, `[${ new Date().toLocaleTimeString() }] ${ message }` ] );
  }, [] );

  const urls = useMemo( () => parseUrls( urlText ), [ urlText ] );

  /** Hash every selected PDF and de-duplicate by digest, not by filename. */
  const addFiles = useCallback( async ( incoming: FileList | File[] ) => {
    const list = Array.from( incoming );
    const pdfs = list.filter( ( file ) => /\.pdf$/i.test( file.name ) );
    const rejected = list.length - pdfs.length;
    if ( rejected > 0 ) addLog( `${ rejected } non-PDF file(s) ignored` );
    if ( !pdfs.length ) return;

    setHashing( true );
    try
    {
      const hashed: PickedFile[] = [];
      for ( const file of pdfs )
      {
        hashed.push( {
          name: file.name,
          size: file.size,
          sha256: await sha256( file ),
          category,
          articleClass,
        } );
      }
      setFiles( ( previous ) => {
        // Digest, not filename. Two exports of the same document under different names are
        // one source, and the ingestion script resolves them that way too — so showing them
        // as two rows here would promise work that will not happen.
        const known = new Set( previous.map( ( item ) => item.sha256 ) );
        const fresh = hashed.filter( ( item ) => !known.has( item.sha256 ) );
        const duplicates = hashed.length - fresh.length;
        if ( duplicates > 0 ) addLog( `${ duplicates } duplicate file(s) skipped (same SHA-256)` );
        if ( fresh.length > 0 ) addLog( `${ fresh.length } PDF(s) added` );
        return [ ...previous, ...fresh ];
      } );
    } catch ( error: any )
    {
      addLog( `Hashing failed: ${ error?.name || 'error' }` );
    } finally
    {
      setHashing( false );
    }
  }, [ addLog, category, articleClass ] );

  const onDrop = useCallback( ( event: React.DragEvent<HTMLDivElement> ) => {
    event.preventDefault();
    setDragging( false );
    if ( event.dataTransfer?.files?.length ) void addFiles( event.dataTransfer.files );
  }, [ addFiles ] );

  const workOrder = useMemo( () => ( {
    generatedAt: new Date().toISOString(),
    standard: 'WECARE.DIGITAL Conversations Content Quality Standard v2',
    category,
    articleClass,
    note: 'Consume with: python scripts/blog_ingest.py ingest --work-order <this file> '
      + '--pdf-dir <directory holding the PDFs>',
    sources: [
      ...files.map( ( file ) => ( {
        sourceType: 'pdf',
        fileName: file.name,
        sha256: file.sha256,
        bytes: file.size,
        category: file.category,
        articleClass: file.articleClass,
      } ) ),
      ...urls.map( ( url ) => ( {
        sourceType: 'url',
        url,
        category,
        articleClass,
      } ) ),
    ],
  } ), [ files, urls, category, articleClass ] );

  const total = files.length + urls.length;

  const download = useCallback( () => {
    const blob = new Blob( [ `${ JSON.stringify( workOrder, null, 2 ) }\n` ],
      { type: 'application/json' } );
    const href = URL.createObjectURL( blob );
    const anchor = document.createElement( 'a' );
    anchor.href = href;
    anchor.download = `work-order-${ new Date().toISOString().slice( 0, 10 ) }.json`;
    anchor.click();
    URL.revokeObjectURL( href );
    addLog( `Work order exported: ${ workOrder.sources.length } source(s)` );
  }, [ workOrder, addLog ] );

  const copyCommand = useCallback( async () => {
    const command = 'python scripts/blog_ingest.py ingest --work-order ~/Downloads/'
      + `work-order-${ new Date().toISOString().slice( 0, 10 ) }.json --pdf-dir <your-pdf-directory>`;
    try
    {
      await navigator.clipboard.writeText( command );
      addLog( 'Ingestion command copied' );
    } catch
    {
      addLog( 'Clipboard unavailable — command shown below' );
    }
  }, [ addLog ] );

  const rollup = useMemo( () => {
    const byStatus: Record<string, number> = {};
    const byCategory: Record<string, number> = {};
    const bySourceType: Record<string, number> = {};
    for ( const row of ledger )
    {
      byStatus[ row.status ] = ( byStatus[ row.status ] || 0 ) + 1;
      if ( row.category ) byCategory[ row.category ] = ( byCategory[ row.category ] || 0 ) + 1;
      bySourceType[ row.sourceType ] = ( bySourceType[ row.sourceType ] || 0 ) + 1;
    }
    return {
      total: ledger.length,
      withArticle: ledger.filter( ( row ) => row.slug ).length,
      pending: ledger.filter( ( row ) => !row.slug && row.status !== 'EXTRACTION_FAILED' ).length,
      failed: ledger.filter( ( row ) => row.status === 'EXTRACTION_FAILED' ).length,
      byStatus, byCategory, bySourceType,
    };
  }, [ ledger ] );

  return (
    <Layout user={ user } onSignOut={ signOut }>
      <SEO title="Blog Studio" description="Bulk PDF and URL intake for the blog" noindex />

      <div style={ { marginBottom: 16 } }>
        <h1 style={ { fontSize: 20, fontWeight: 700, margin: 0 } }>Blog Studio</h1>
        <p style={ { fontSize: 13, color: '#6b7280', margin: '4px 0 0' } }>
          Bulk PDF and URL intake under the Conversations Content Quality Standard v2.
        </p>
      </div>

      <div style={ { display: 'flex', gap: 6, marginBottom: 16, flexWrap: 'wrap' } }>
        { ( [
          [ 'intake', `Intake${ total ? ` (${ total })` : '' }` ],
          [ 'ledger', `Source ledger${ ledger.length ? ` (${ ledger.length })` : '' }` ],
          [ 'standard', 'What is checked' ],
        ] as [ Tab, string ][] ).map( ( [ id, text ] ) => (
          <button key={ id } onClick={ () => setTab( id ) }
            style={ {
              ...btn,
              background: tab === id ? '#d1f470' : '#f3f4f6',
              fontWeight: tab === id ? 600 : 400,
            } }>
            { text }
          </button>
        ) ) }
      </div>

      { tab === 'intake' && (
        <div style={ { maxWidth: 940 } }>
          <div className="card" style={ { padding: 20, marginBottom: 16 } }>
            <div style={ { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 } }>
              <div>
                <label style={ label } htmlFor="blog-studio-category">Category</label>
                <select id="blog-studio-category" value={ category } style={ input }
                  onChange={ ( event ) => setCategory( event.target.value as Category ) }>
                  { CATEGORIES.map( ( value ) => <option key={ value } value={ value }>{ value }</option> ) }
                </select>
                <div style={ { fontSize: 11, color: '#9ca3af', marginTop: 4 } }>
                  The only two categories on the live site. Applied to sources added next.
                </div>
              </div>
              <div>
                <label style={ label } htmlFor="blog-studio-class">Article class</label>
                <select id="blog-studio-class" value={ articleClass } style={ input }
                  onChange={ ( event ) => setArticleClass( event.target.value as ArticleClass ) }>
                  { ARTICLE_CLASSES.map( ( value ) => <option key={ value } value={ value }>{ value }</option> ) }
                </select>
                <div style={ { fontSize: 11, color: '#9ca3af', marginTop: 4 } }>
                  ARCHIVE_DERIVED gets a fresh slug and today&apos;s publication date.
                  ORIGINAL_109 preserves both.
                </div>
              </div>
            </div>

            <label style={ label }>PDF sources</label>
            <div
              onDragOver={ ( event ) => { event.preventDefault(); setDragging( true ); } }
              onDragLeave={ () => setDragging( false ) }
              onDrop={ onDrop }
              onClick={ () => fileInput.current?.click() }
              role="button"
              tabIndex={ 0 }
              onKeyDown={ ( event ) => {
                if ( event.key === 'Enter' || event.key === ' ' ) fileInput.current?.click();
              } }
              aria-label="Add PDF files"
              style={ {
                border: `2px dashed ${ dragging ? '#84cc16' : '#e5e7eb' }`,
                background: dragging ? '#f7fee7' : '#fafafa',
                borderRadius: 10, padding: '28px 16px', textAlign: 'center', cursor: 'pointer',
              } }>
              <div style={ { fontSize: 13, fontWeight: 600, color: '#374151' } }>
                { hashing ? 'Hashing…' : 'Drop PDFs here, or click to choose' }
              </div>
              <div style={ { fontSize: 11, color: '#9ca3af', marginTop: 4 } }>
                Many files at once. Nothing is uploaded — each file is read locally to
                compute its SHA-256.
              </div>
            </div>
            <input ref={ fileInput } type="file" accept="application/pdf,.pdf" multiple
              style={ { display: 'none' } }
              onChange={ ( event ) => {
                if ( event.target.files ) void addFiles( event.target.files );
                event.target.value = '';
              } } />

            { files.length > 0 && (
              <div style={ { marginTop: 12, overflowX: 'auto' } }>
                <table style={ { width: '100%', borderCollapse: 'collapse' } }>
                  <thead>
                    <tr>
                      <th style={ th } scope="col">File</th>
                      <th style={ th } scope="col">Size</th>
                      <th style={ th } scope="col">SHA-256</th>
                      <th style={ th } scope="col">Category</th>
                      <th style={ th } scope="col" />
                    </tr>
                  </thead>
                  <tbody>
                    { files.map( ( file ) => (
                      <tr key={ file.sha256 } style={ { borderBottom: '1px solid #f3f4f6' } }>
                        <td style={ td }>{ file.name }</td>
                        <td style={ td }>{ formatBytes( file.size ) }</td>
                        <td style={ { ...td, fontFamily: 'ui-monospace, monospace', fontSize: 11 } }>
                          { file.sha256.slice( 0, 12 ) }…
                        </td>
                        <td style={ td }>{ file.category }</td>
                        <td style={ td }>
                          <button style={ { ...btn, background: '#f3f4f6', padding: '2px 8px' } }
                            onClick={ () => setFiles(
                              ( previous ) => previous.filter( ( item ) => item.sha256 !== file.sha256 ) ) }>
                            Remove
                          </button>
                        </td>
                      </tr>
                    ) ) }
                  </tbody>
                </table>
              </div>
            ) }

            <div style={ { marginTop: 16 } }>
              <label style={ label } htmlFor="blog-studio-urls">URL sources</label>
              <textarea id="blog-studio-urls" value={ urlText } rows={ 6 }
                onChange={ ( event ) => setUrlText( event.target.value ) }
                placeholder={ '# one per line, comments allowed\nhttps://example.com/an-article' }
                style={ { ...input, fontFamily: 'ui-monospace, monospace', fontSize: 12, resize: 'vertical' } } />
              <div style={ { fontSize: 11, color: '#6b7280', marginTop: 4 } }>
                { urls.length } URL(s) recognised. A URL that serves a PDF is handled as a PDF.
              </div>
            </div>
          </div>

          <div className="card" style={ { padding: 20, marginBottom: 16 } }>
            <h2 style={ { fontSize: 14, fontWeight: 700, margin: '0 0 8px' } }>
              Export the work order
            </h2>
            <p style={ { fontSize: 12, color: '#6b7280', margin: '0 0 12px' } }>
              { total === 0
                ? 'Add at least one source.'
                : `${ files.length } PDF(s) and ${ urls.length } URL(s) ready. `
                + 'The exported file records each source, its category and its SHA-256. '
                + 'Ingestion re-checks that hash against the file on disk and refuses a '
                + 'mismatch, so a wrongly selected file cannot become permanent provenance.' }
            </p>
            <div style={ { display: 'flex', gap: 8, flexWrap: 'wrap' } }>
              <button onClick={ download } disabled={ total === 0 }
                style={ { ...btn, background: total === 0 ? '#f3f4f6' : '#d1f470', fontWeight: 600 } }>
                Download work order
              </button>
              <button onClick={ copyCommand } style={ { ...btn, background: '#f3f4f6' } }>
                Copy ingestion command
              </button>
              <button style={ { ...btn, background: '#f3f4f6' } }
                onClick={ () => { setFiles( [] ); setUrlText( '' ); addLog( 'Cleared' ); } }>
                Clear
              </button>
            </div>
            <pre style={ {
              background: '#f9fafb', padding: 12, borderRadius: 8, fontSize: 11, lineHeight: 1.7,
              margin: '12px 0 0', whiteSpace: 'pre-wrap', color: '#374151',
            } }>{ `python scripts/blog_ingest.py ingest \\
    --work-order ~/Downloads/work-order-<date>.json \\
    --pdf-dir <directory holding the PDFs> --workers 8

python scripts/blog_ingest.py status
python scripts/blog_ingest.py draft --out content/conversations/drafts/CONV-001-CONV-025.json --limit 25

# after the editorial pass
python scripts/blog_quality_v2.py validate --manifest content/conversations/batches/CONV-001-CONV-025.json` }</pre>
          </div>

          { log.length > 0 && (
            <div className="card" style={ { padding: 16 } }>
              <h2 style={ { fontSize: 13, fontWeight: 600, margin: '0 0 8px' } }>Activity</h2>
              <div style={ {
                fontFamily: 'ui-monospace, monospace', fontSize: 11, color: 'rgba(0,0,0,.54)',
                maxHeight: 160, overflowY: 'auto',
              } }>
                { log.map( ( line, index ) => <div key={ index }>{ line }</div> ) }
              </div>
            </div>
          ) }
        </div>
      ) }

      { tab === 'ledger' && (
        <div style={ { maxWidth: 1100 } }>
          <div className="card" style={ { padding: 20, marginBottom: 16 } }>
            <h2 style={ { fontSize: 14, fontWeight: 700, margin: '0 0 4px' } }>
              Which article came from which source
            </h2>
            <p style={ { fontSize: 12, color: '#6b7280', margin: '0 0 12px' } }>
              Read from <code>content/conversations/ledger.json</code> at build time.
              { ledgerUpdatedAt ? ` Ledger updated ${ ledgerUpdatedAt }.` : '' }
              { ' ' }Because the site is a static export, this reflects the last build — run
              the ingestion script and rebuild to refresh it.
            </p>
            { !ledgerPresent ? (
              <div style={ { fontSize: 12, color: '#6b7280' } }>
                No ledger committed yet. It is created by the first{ ' ' }
                <code>blog_ingest.py ingest</code> run.
              </div>
            ) : (
              <div style={ { display: 'flex', gap: 24, flexWrap: 'wrap', fontSize: 12 } }>
                { ( [
                  [ 'Sources', rollup.total ],
                  [ 'With an article', rollup.withArticle ],
                  [ 'Awaiting an article', rollup.pending ],
                  [ 'Extraction failed', rollup.failed ],
                ] as [ string, number ][] ).map( ( [ text, value ] ) => (
                  <div key={ text }>
                    <div style={ { fontSize: 20, fontWeight: 700 } }>{ value }</div>
                    <div style={ { color: '#6b7280' } }>{ text }</div>
                  </div>
                ) ) }
              </div>
            ) }
          </div>

          { ledger.length > 0 && (
            <div className="card" style={ { padding: 0, overflowX: 'auto' } }>
              <table style={ { width: '100%', borderCollapse: 'collapse' } }>
                <thead>
                  <tr>
                    <th style={ th } scope="col">Source</th>
                    <th style={ th } scope="col">Type</th>
                    <th style={ th } scope="col">Words</th>
                    <th style={ th } scope="col">Category</th>
                    <th style={ th } scope="col">Status</th>
                    <th style={ th } scope="col">Article</th>
                  </tr>
                </thead>
                <tbody>
                  { ledger.map( ( row ) => (
                    <tr key={ row.sourceSha256 } style={ { borderBottom: '1px solid #f3f4f6' } }>
                      <td style={ td }>
                        <div style={ { wordBreak: 'break-all' } }>{ row.sourceRef }</div>
                        { row.sourceTitle && (
                          <div style={ { color: '#9ca3af', fontSize: 11 } }>{ row.sourceTitle }</div>
                        ) }
                        { row.error && (
                          <div style={ { color: '#b91c1c', fontSize: 11 } }>{ row.error }</div>
                        ) }
                      </td>
                      <td style={ td }>{ row.sourceType }</td>
                      <td style={ td }>{ row.extractedWords || '—' }</td>
                      <td style={ td }>{ row.category || '—' }</td>
                      <td style={ td }>{ row.status }</td>
                      <td style={ td }>
                        { row.slug
                          ? <a href={ `https://wecare.digital/post/${ row.slug }/` }
                            rel="noopener noreferrer" target="_blank">{ row.slug }</a>
                          : <span style={ { color: '#9ca3af' } }>not written yet</span> }
                      </td>
                    </tr>
                  ) ) }
                </tbody>
              </table>
            </div>
          ) }
        </div>
      ) }

      { tab === 'standard' && (
        <div style={ { maxWidth: 820 } }>
          <div className="card" style={ { padding: 20, marginBottom: 16 } }>
            <h2 style={ { fontSize: 14, fontWeight: 700, margin: '0 0 8px' } }>
              The pipeline cannot approve an article
            </h2>
            <p style={ { fontSize: 13, color: '#374151', lineHeight: 1.7, margin: '0 0 12px' } }>
              Section 29 of the standard asks for a verdict on whether the writing is
              independently Anew rather than cosmetically rewritten, on whether it sounds
              like WECARE.DIGITAL, and on whether the material deserves its own article.
              Section 30 asks whether a reader would feel it was written because there was
              something worth saying. No program can answer those.
            </p>
            <p style={ { fontSize: 13, color: '#374151', lineHeight: 1.7, margin: 0 } }>
              So the automated checks only ever move a record <strong>down</strong>. A
              record that passes every one of them lands on <code>EDITORIAL_QA</code>.
              Reaching <code>READY_TO_PUBLISH</code> — the only status that may enter the
              Wix queue — requires a person to have recorded the eleven human gates.
            </p>
          </div>

          <div style={ { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 } }>
            <div className="card" style={ { padding: 16 } }>
              <h3 style={ { fontSize: 13, fontWeight: 700, margin: '0 0 8px' } }>
                Decided automatically
              </h3>
              <ul style={ { fontSize: 12, color: '#374151', lineHeight: 1.9, paddingLeft: 18, margin: 0 } }>
                { MACHINE_GATES.map( ( name ) => <li key={ name }><code>{ name }</code></li> ) }
              </ul>
              <p style={ { fontSize: 11, color: '#6b7280', margin: '10px 0 0', lineHeight: 1.6 } }>
                Plus every mechanical clause: provenance and source hash, the length bands,
                the stock-phrase and self-help detectors, sentence-cadence uniformity,
                false-biography and unattributed-quotation detection, factual-review flags,
                slug and date rules per class, canonical and tag rules, the fixed author and
                the two categories, legacy markup, the image ban, and corpus-wide
                duplication by slug, title and body shingle.
              </p>
            </div>
            <div className="card" style={ { padding: 16 } }>
              <h3 style={ { fontSize: 13, fontWeight: 700, margin: '0 0 8px' } }>
                Requires a human verdict
              </h3>
              <ul style={ { fontSize: 12, color: '#374151', lineHeight: 1.9, paddingLeft: 18, margin: 0 } }>
                { HUMAN_GATES.map( ( name ) => <li key={ name }><code>{ name }</code></li> ) }
              </ul>
            </div>
          </div>

          <div className="card" style={ { padding: 16, marginTop: 16 } }>
            <h3 style={ { fontSize: 13, fontWeight: 700, margin: '0 0 8px' } }>
              Publication stays gated, and stays two-phase
            </h3>
            <p style={ { fontSize: 12, color: '#374151', lineHeight: 1.7, margin: 0 } }>
              Nothing on this page publishes. Conversations go out through{ ' ' }
              <code>wix_blog_migrate.py apply --mode publish</code>, whose default mode
              mutates nothing; Gastronomy through the <code>publish</code> input on the
              content-gate workflow. And because the public site is a static export, a
              published post is not visible until an Amplify build re-reads Wix.
            </p>
          </div>
        </div>
      ) }
    </Layout>
  );
};

/**
 * The committed ledger, read at build time.
 *
 * `node:fs` is imported inside the function rather than at module scope so it never
 * reaches the client bundle. A missing or malformed ledger yields an empty table rather
 * than failing the build: this is an internal admin view, and an unreadable working file
 * must not be able to stop the public site from building.
 */
export async function getStaticProps () {
  const fallback = { ledger: [], ledgerUpdatedAt: '', ledgerPresent: false };
  try
  {
    const [ { default: fs }, { default: path } ] = await Promise.all( [
      import( 'node:fs' ), import( 'node:path' ),
    ] );
    const file = path.join( process.cwd(), 'content', 'conversations', 'ledger.json' );
    if ( !fs.existsSync( file ) ) return { props: fallback };
    const document = JSON.parse( fs.readFileSync( file, 'utf8' ) );
    const rows = Array.isArray( document?.sources ) ? document.sources : [];
    return {
      props: {
        ledgerPresent: true,
        ledgerUpdatedAt: String( document?.updatedAt || '' ),
        ledger: rows.map( ( row: any ) => ( {
          sourceType: String( row?.sourceType || '' ),
          sourceRef: String( row?.sourceRef || '' ),
          sourceSha256: String( row?.sourceSha256 || '' ),
          status: String( row?.status || '' ),
          category: String( row?.category || '' ),
          slug: String( row?.slug || '' ),
          title: String( row?.title || '' ),
          sourceTitle: String( row?.sourceTitle || '' ),
          extractedWords: Number( row?.extractedWords || 0 ),
          batchFile: String( row?.batchFile || '' ),
          publishedAt: String( row?.publishedAt || '' ),
          error: String( row?.error || '' ),
        } ) ),
      },
    };
  } catch
  {
    return { props: fallback };
  }
}

export default BlogStudio;
