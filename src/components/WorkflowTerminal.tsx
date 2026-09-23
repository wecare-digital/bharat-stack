import React, { useEffect, useRef, useState } from 'react';

/**
 * Animated workflow terminal, from the owner's HTML mock, restyled onto the site.
 *
 * SELF-STYLING, like BrandBadge and RotatingHero: styled-jsx cannot scope a composite
 * component from its parent, so this owns every rule it needs and the consumer owns
 * nothing but placement.
 *
 * COLOURS ARE ALL EXISTING VALUES. The mock shipped its own palette - #17191c panel,
 * #659df5 blue, #57c785 green, #dab25f yellow, #a294ff purple, #d98787 red. None of
 * those are in this site's palette, and the design contract already records that
 * inventing in-between values is how #f2fbf6, #fbfff0 and the whole #1e293b slate ramp
 * got here and had to be retired. So the mapping is:
 *
 *   panel        #000                     both existing code panels are #000
 *   panel edge   1.5px rgba(255,255,255,.92)  the documented editor-pane stroke
 *   base text    #fff
 *   muted        rgba(255,255,255,.54)    the value .pp-tab already uses idle
 *   accent       #d1f470                  lime, our own surface - the owner's ask
 *   warning      #f0a818                  the existing amber dot
 *   removed      #dc2626                  the existing red dot
 *   mono         'SF Mono',Monaco,Consolas,monospace   as .code-body
 *
 * That loses the mock's syntax rainbow on purpose: one accent doing the work reads as
 * this site, five borrowed hues read as a different product embedded in it.
 *
 * THE STREAM IS aria-hidden AND GATED. It is illustrative, so a screen reader gets one
 * static summary instead of a stream of appearing nodes. It also only animates while
 * on screen and never under reduced motion - the mock looped forever unconditionally,
 * which on a homepage means a timer burning battery in a background tab.
 */

type Result = { label: string; kind?: 'ok' | 'warn' };

interface Step {
  name: string;
  description: string;
  time: string;
  command?: React.ReactNode;
  results?: Result[];
  diff?: { title: string; lines: Array<{ add?: boolean; text: string }> };
  checks?: string[];
  thinking?: boolean;
  complete?: boolean;
}

const STEPS: Step[] = [
  { name: 'Plan', time: '0.4s', description: 'Map the workflow, dependencies, and shortest safe execution path.' },
  {
    name: 'Read configuration', time: '0.6s',
    description: 'Loaded workflow rules, tools, retry policy, and validation logic.',
    results: [ { label: 'workflow.ts' }, { label: 'tools.ts' }, { label: 'retry.ts' }, { label: 'checks.ts' } ],
  },
  {
    name: 'Call tool', time: '0.8s',
    description: 'Check the current customer state before continuing.',
    command: <><span className="wt-sh">$</span><span className="wt-fn">crm.lookup</span>(<span className="wt-str">&quot;customer_2841&quot;</span>)</>,
  },
  {
    name: 'Inspect result', time: '0.3s', thinking: true,
    description: 'The response is valid, but required onboarding context is incomplete.',
    results: [ { label: '24 records' }, { label: 'confidence 0.71', kind: 'warn' }, { label: 'context incomplete', kind: 'warn' } ],
  },
  {
    name: 'Retry', time: '0.9s',
    description: 'Expand lookup depth only for the incomplete operation.',
    command: <><span className="wt-sh">$</span><span className="wt-fn">crm.lookup</span>({ '{' } <span className="wt-key">id</span>: <span className="wt-str">&quot;customer_2841&quot;</span>, <span className="wt-key">depth</span>: <span className="wt-num">2</span> { '}' })</>,
    results: [ { label: '37 records', kind: 'ok' }, { label: 'confidence 0.94', kind: 'ok' } ],
  },
  {
    name: 'Optimize', time: '0.5s',
    description: 'Remove unnecessary sequential work and reuse resolved context.',
    diff: {
      title: 'workflow.ts',
      lines: [
        { text: 'await loadProfile();' },
        { text: 'await loadPreferences();' },
        { add: true, text: 'await Promise.all([loadProfile(), loadPreferences()]);' },
        { add: true, text: 'context.cache(customer);' },
      ],
    },
  },
  {
    name: 'Run checks', time: '1.1s',
    description: 'Verify the optimized execution path before completion.',
    checks: [ 'workflow.test', 'retry.test', 'latency.test' ],
  },
  {
    name: 'Complete', time: '3.8s', complete: true,
    description: 'Workflow completed with fewer calls and lower execution time.',
    results: [ { label: '8 → 5 calls', kind: 'ok' }, { label: '6.2s → 3.8s', kind: 'ok' }, { label: '39% faster', kind: 'ok' } ],
  },
];

// Per-step dwell, from the mock: richer steps hold longer so there is time to read
// them. Keyed off what the step contains rather than its index, so reordering STEPS
// does not silently retime the sequence.
const dwell = ( step: Step ): number => {
  if ( step.diff ) return 1550;
  if ( step.complete ) return 1500;
  if ( step.checks ) return 1450;
  if ( step.command ) return 1350;
  if ( step.thinking ) return 1250;
  return 900;
};

const WorkflowTerminal: React.FC = () => {
  // How many steps are on screen, and whether the last of them is still running.
  const [ shown, setShown ] = useState( 0 );
  const [ settled, setSettled ] = useState( -1 );
  const [ done, setDone ] = useState( false );
  const [ run, setRun ] = useState( false );
  const rootRef = useRef<HTMLDivElement | null>( null );
  const streamRef = useRef<HTMLDivElement | null>( null );

  // Only animate while visible, and never under reduced motion. The mock ran an
  // unconditional infinite loop; on a homepage that is a timer in a background tab.
  //
  // Every state change here is SCHEDULED rather than called in the effect body.
  // Writing setShown/setRun straight into the body is the
  // react-hooks/set-state-in-effect error - the repo already carries 116 of those and
  // this file is not adding more. It cannot be hoisted into a lazy useState initialiser
  // either, because both branches read browser-only globals (matchMedia,
  // IntersectionObserver) that are undefined during the static export and would
  // hydrate to a different value than they render to. A timeout of 0 resolves both:
  // the decision happens after commit, on the client, one frame later than paint,
  // which is invisible for an element that starts empty anyway.
  useEffect( () => {
    let cancelled = false;
    let io: IntersectionObserver | null = null;

    const id = window.setTimeout( () => {
      if ( cancelled ) return;

      const reduce = typeof window.matchMedia === 'function'
        && window.matchMedia( '(prefers-reduced-motion: reduce)' ).matches;
      if ( reduce ) {
        // Show the finished state outright: the sequence is the decoration, the
        // content is not.
        setShown( STEPS.length );
        setSettled( STEPS.length );
        setDone( true );
        return;
      }

      const node = rootRef.current;
      if ( !node || typeof IntersectionObserver !== 'function' ) { setRun( true ); return; }
      io = new IntersectionObserver(
        entries => entries.forEach( entry => setRun( entry.isIntersecting ) ),
        { threshold: 0.25 }
      );
      io.observe( node );
    }, 0 );

    return () => { cancelled = true; window.clearTimeout( id ); if ( io ) io.disconnect(); };
  }, [] );

  // The sequence. One chained timeout rather than an interval, so a slow frame cannot
  // stack two steps on top of each other.
  useEffect( () => {
    if ( !run ) return undefined;
    let cancelled = false;
    let timer = 0;

    const step = ( index: number ) => {
      if ( cancelled ) return;
      if ( index >= STEPS.length ) {
        setDone( true );
        timer = window.setTimeout( () => {
          if ( cancelled ) return;
          setShown( 0 ); setSettled( -1 ); setDone( false );
          timer = window.setTimeout( () => step( 0 ), 650 );
        }, 3200 );
        return;
      }
      setShown( index + 1 );
      timer = window.setTimeout( () => {
        if ( cancelled ) return;
        setSettled( index );
        timer = window.setTimeout( () => step( index + 1 ), 250 );
      }, dwell( STEPS[ index ] ) );
    };

    timer = window.setTimeout( () => step( 0 ), 600 );
    return () => { cancelled = true; window.clearTimeout( timer ); };
  }, [ run ] );

  // Follow the stream, but inside the panel only - never scroll the page.
  useEffect( () => {
    const el = streamRef.current;
    if ( el && el.parentElement ) el.parentElement.scrollTop = el.parentElement.scrollHeight;
  }, [ shown, settled ] );

  const visible = STEPS.slice( 0, shown );

  return (
    <section className="wt-wrap" ref={ rootRef } aria-label="How a workflow runs">
      {/* One static sentence for assistive tech. The stream below is aria-hidden: a
          screen reader should not receive eight nodes appearing on timers. */}
      <p className="wt-sr">
        An illustration of an automated workflow: plan, read configuration, call a tool,
        inspect the result, retry with more depth, optimise, run checks, complete —
        reducing eight calls to five and 6.2 seconds to 3.8.
      </p>

      <div className="wt-window" aria-hidden="true">
        <div className="wt-bar">
          <span className="wt-light wt-red" />
          <span className="wt-light wt-amber" />
          <span className="wt-light wt-lime" />
          <span className="wt-bar-title">workflow / production</span>
          <span className="wt-bar-state"><i className="wt-state-dot" />optimized execution</span>
        </div>

        <div className="wt-space">
          <div className="wt-request"><span className="wt-caret">›</span><span>Optimize customer onboarding and verify the execution path.</span></div>

          <div ref={ streamRef }>
            { visible.map( ( step, i ) => {
              const state = i <= settled ? 'is-done' : 'is-running';
              const last = i === STEPS.length - 1;
              return (
                <div key={ step.name } className={ `wt-step ${state} ${last ? 'is-last' : ''}`.trim() }>
                  <span className="wt-dot" />
                  <div className="wt-head">
                    <span className={ `wt-name ${step.complete ? 'is-complete' : ''}`.trim() }>
                      { step.thinking && <span className="wt-spark">✦</span> }
                      { step.complete && <span className="wt-tick">✓ </span> }
                      { step.name }
                    </span>
                    <span className="wt-time">{ step.time }</span>
                  </div>
                  <p className="wt-desc">{ step.description }</p>

                  { step.command && <div className="wt-cmd">{ step.command }</div> }

                  { step.results && (
                    <div className="wt-results">
                      { step.results.map( r => (
                        <span key={ r.label } className={ `wt-chip ${r.kind ? 'is-' + r.kind : ''}`.trim() }>{ r.label }</span>
                      ) ) }
                    </div>
                  ) }

                  { step.diff && (
                    <div className="wt-diff">
                      <div className="wt-diff-title">{ step.diff.title }</div>
                      { step.diff.lines.map( line => (
                        <div key={ line.text } className={ `wt-diff-line ${line.add ? 'is-add' : 'is-del'}` }>
                          <span className="wt-diff-sign">{ line.add ? '+' : '-' }</span>{ line.text }
                        </div>
                      ) ) }
                    </div>
                  ) }

                  { step.checks && (
                    <div className="wt-checks">
                      { step.checks.map( c => (
                        <div key={ c } className="wt-check"><span className="wt-check-tick">✓</span>{ c }</div>
                      ) ) }
                    </div>
                  ) }
                </div>
              );
            } ) }
          </div>
        </div>

        {/* OUTSIDE .wt-space, deliberately. In the original mock this footer sits
            inside the scrolling workspace as position:absolute;bottom:0 - and an
            absolutely positioned element in a scroll container anchors to the bottom of
            the SCROLLED CONTENT, not to the visible box. So once the stream grew past
            the panel height the status bar rendered in the middle of the list, on top
            of the steps. It only reproduces after enough rows have streamed in, which
            is why it survived in the mock and why a screenshot caught it here rather
            than an assertion.
            As a flex sibling of the scroll area it is pinned to the window for free,
            and the gradient becomes unnecessary - a solid panel-coloured bar with a
            hairline above it is what actually separates the two. */}
        <div className="wt-foot">
          <span className="wt-foot-left"><i className="wt-foot-dot" />{ done ? 'complete' : 'running' }</span>
          <span className="wt-foot-right">{ done ? '5 calls · 1 retry · 3.8s' : `${shown} / ${STEPS.length} operations` }</span>
        </div>
      </div>

      <style jsx>{`
        .wt-wrap{width:100%}
        .wt-sr{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}

        /* #000 with the 1.5px white stroke: the documented editor-pane treatment the
           two existing code panels already use, rather than the mock's #17191c and a
           grey border. radius 14px matches them too. */
        .wt-window{
          width:100%;height:650px;display:flex;flex-direction:column;overflow:hidden;
          background:#000;border:1.5px solid rgba(255,255,255,.92);border-radius:14px;
          box-shadow:0 30px 80px rgba(0,0,0,.08),0 5px 18px rgba(0,0,0,.04);
          font-family:'SF Mono',Monaco,Consolas,monospace;
        }

        /* Title bar stays light, as in the mock - it reads as chrome around the panel
           rather than part of it. The three lights reuse the existing red and amber
           dots and lime, instead of macOS #ff5f57/#febc2e/#28c840. */
        .wt-bar{height:47px;flex-shrink:0;display:flex;align-items:center;gap:8px;padding:0 15px;background:#fafafa;border-bottom:1px solid #e5e7eb}
        .wt-light{width:11px;height:11px;border-radius:50%;flex:0 0 auto}
        .wt-red{background:#dc2626}
        .wt-amber{background:#f0a818}
        .wt-lime{background:#d1f470}
        .wt-bar-title{margin-left:8px;color:rgba(0,0,0,.54);font-size:11px}
        .wt-bar-state{margin-left:auto;display:flex;align-items:center;gap:7px;color:rgba(0,0,0,.42);font-size:10px}
        .wt-state-dot{width:6px;height:6px;border-radius:50%;background:#d1f470}

        /* min-height:0 is load-bearing on a flex child that scrolls: without it the
           flex item's automatic minimum size is its content, so it refuses to shrink,
           the panel grows past its 650px and nothing ever scrolls. Bottom padding is
           24px now rather than 66px - the 66 was reserving room for a footer that used
           to overlap this box and no longer does. */
        .wt-space{position:relative;flex:1;min-height:0;padding:30px 34px 24px;overflow-y:auto;overflow-x:hidden;scrollbar-width:thin;scrollbar-color:rgba(255,255,255,.24) transparent}
        .wt-space::-webkit-scrollbar{width:7px}
        .wt-space::-webkit-scrollbar-thumb{background:rgba(255,255,255,.24);border-radius:20px}

        .wt-request{margin-bottom:32px;display:flex;gap:10px;color:#fff;font-size:13px;line-height:1.7}
        .wt-caret{color:#d1f470}

        /* Each step fades up as it arrives. The connector is a ::before rule so it
           cannot be knocked out of alignment by content height. */
        .wt-step{position:relative;padding:0 0 29px 36px;opacity:1;transform:translateY(0);animation:wt-in .35s ease both}
        .wt-step::before{content:'';position:absolute;left:5px;top:19px;bottom:-1px;width:1px;background:rgba(255,255,255,.16)}
        .wt-step.is-last::before{display:none}
        @keyframes wt-in{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}

        .wt-dot{position:absolute;left:0;top:4px;width:12px;height:12px;z-index:2;border-radius:50%;border:2px solid rgba(255,255,255,.34);background:#000}
        /* Running is lime and pulses; settled is solid lime. The mock used blue for
           running and green for done - one accent carries both states here. */
        .wt-step.is-running .wt-dot{border-color:#d1f470;background:#d1f470;box-shadow:0 0 0 4px rgba(209,244,112,.14);animation:wt-pulse 1.2s ease-in-out infinite}
        .wt-step.is-done .wt-dot{border-color:#d1f470;background:#d1f470}
        @keyframes wt-pulse{0%,100%{opacity:.5;transform:scale(.85)}50%{opacity:1;transform:scale(1)}}

        .wt-head{min-height:20px;display:flex;align-items:center;gap:10px}
        .wt-name{color:#fff;font-size:13px;font-weight:600}
        .wt-name.is-complete{color:#d1f470}
        .wt-tick{color:#d1f470}
        .wt-spark{color:#d1f470;display:inline-block;margin-right:6px;animation:wt-spin 1.8s linear infinite}
        @keyframes wt-spin{to{transform:rotate(360deg)}}
        .wt-time{color:rgba(255,255,255,.42);font-size:10px}
        .wt-desc{max-width:780px;margin:6px 0 0;color:rgba(255,255,255,.54);font-size:11px;line-height:1.7}

        .wt-cmd{margin-top:11px;padding:11px 13px;overflow-x:auto;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.14);border-radius:7px;color:#fff;font-size:11px;line-height:1.7;white-space:nowrap}
        .wt-sh{margin-right:7px;color:rgba(255,255,255,.42)}
        .wt-fn{color:#d1f470}
        .wt-str{color:rgba(255,255,255,.72)}
        .wt-key{color:rgba(255,255,255,.54)}
        .wt-num{color:#d1f470}

        .wt-results{margin-top:10px;display:flex;flex-wrap:wrap;gap:7px}
        .wt-chip{padding:5px 8px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.14);border-radius:5px;color:rgba(255,255,255,.54);font-size:10px}
        .wt-chip.is-ok{color:#d1f470;border-color:rgba(209,244,112,.34)}
        .wt-chip.is-warn{color:#f0a818;border-color:rgba(240,168,24,.3)}

        .wt-diff{margin-top:11px;overflow:hidden;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.14);border-radius:7px;font-size:10px}
        .wt-diff-title{padding:8px 11px;color:rgba(255,255,255,.42);border-bottom:1px solid rgba(255,255,255,.14)}
        .wt-diff-line{padding:5px 11px;line-height:1.55;white-space:nowrap;overflow-x:auto}
        .wt-diff-line.is-del{color:#dc2626;background:rgba(220,38,38,.08)}
        .wt-diff-line.is-add{color:#d1f470;background:rgba(209,244,112,.08)}
        .wt-diff-sign{display:inline-block;width:17px;opacity:.7}

        .wt-checks{margin-top:10px;display:grid;gap:7px}
        .wt-check{display:flex;align-items:center;gap:8px;color:rgba(255,255,255,.54);font-size:10px}
        .wt-check-tick{color:#d1f470}

        /* Fades the stream out under the footer rather than letting rows collide with
           it. The gradient has to end in the panel's own #000 or it shows a seam. */
        .wt-foot{flex:0 0 auto;height:50px;padding:0 24px;display:flex;align-items:center;background:#000;border-top:1px solid rgba(255,255,255,.14);color:rgba(255,255,255,.42);font-size:10px}
        .wt-foot-left{display:flex;align-items:center;gap:7px}
        .wt-foot-dot{width:5px;height:5px;border-radius:50%;background:#d1f470}
        .wt-foot-right{margin-left:auto}

        @media(max-width:767px){
          .wt-window{height:min(560px,calc(100vh - 180px));border-radius:12px}
          .wt-space{padding:23px 18px 60px}
          .wt-bar-state{display:none}
          .wt-step{padding-left:29px}
          .wt-request{font-size:12px}
        }

        /* The sequence is already short-circuited in JS - every step is rendered at
           once - so this only has to stop the decorative loops. */
        @media(prefers-reduced-motion:reduce){
          .wt-step{animation:none}
          .wt-step.is-running .wt-dot,.wt-spark{animation:none}
          .wt-space{scroll-behavior:auto}
        }
      `}</style>
    </section>
  );
};

export default WorkflowTerminal;
