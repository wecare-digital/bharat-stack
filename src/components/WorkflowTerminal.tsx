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
 * inventing in-between values is how #f2fbf6, #fbfff0 and the whole #000 slate ramp
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
type Lane = { name: string; detail: string };

interface Step {
  /** The service that did the work, shown as the lane label. */
  service: string;
  name: string;
  description: string;
  time: string;
  /** Shared infrastructure this step ran on, rendered as a code comment. */
  infra?: string;
  command?: React.ReactNode;
  results?: Result[];
  /** Concurrent services. Rendered as parallel lanes, not a sequence. */
  lanes?: Lane[];
  checks?: string[];
  complete?: boolean;
}

/**
 * WHAT THIS PANEL SAYS ABOUT THE COMPANY, which is the whole reason it was rewritten.
 *
 * It used to run an agent loop: Plan, Read configuration, Call tool, Inspect result,
 * "confidence 0.71", Retry, Optimize, Run checks. Every one of those beats is the visual
 * grammar of an autonomous-agent demo, and a visitor reading it would reasonably conclude
 * this is an agentic AI product. The owner's position is the opposite: WECARE.DIGITAL runs
 * many services on one shared platform, and the AI parts are a feature of a few of them,
 * not the thing being sold.
 *
 * So the stream now shows what the backend actually does on a single request - gateway,
 * auth, contacts, four messaging workers in parallel, commerce, billing, the queue
 * absorbing a provider failure, and the health rollup. These are the real service
 * families in this repo (amplify/functions/{core,messaging,ecommerce,operations}), not
 * invented ones.
 *
 * THE INFRA IS NAMED IN COMMENT LINES. Each step carries a "#" line listing the shared
 * components it used, which is what makes the point the headline makes in words: the
 * services are different, the foundation underneath them is the same one. The parallel
 * lanes in the messaging step exist to show concurrency directly - a vertical list would
 * have read as four more sequential steps, which is precisely the wrong impression.
 *
 * Nothing here claims a benchmark. The timings are illustrative and the panel is
 * aria-hidden with a static summary, so no assistive technology is told these are
 * measurements.
 */
const STEPS: Step[] = [
  {
    service: 'gateway', name: 'Request accepted', time: '12ms',
    description: 'One HTTPS request arrives and is routed to the handler for this account.',
    infra: 'api gateway · lambda · tls terminated at the edge',
  },
  {
    service: 'auth', name: 'Account resolved', time: '31ms',
    description: 'The caller is verified and scoped, so every later step is limited to their data.',
    infra: 'cognito · iam · per-account isolation',
    results: [ { label: 'verified', kind: 'ok' }, { label: 'scope: account_2841' } ],
  },
  {
    service: 'contacts', name: 'Customer looked up', time: '18ms',
    description: 'A single-key read returns the customer and the channels they agreed to.',
    infra: 'dynamodb · single-table · on-demand capacity',
    command: <><span className="wt-sh">$</span><span className="wt-fn">contacts.get</span>(<span className="wt-str">&quot;cust_2841&quot;</span>) <span className="wt-cm">— 1 read unit</span></>,
  },
  {
    service: 'messaging', name: 'Four services pick it up at once', time: '46ms',
    description: 'Independent workers run in parallel. None of them waits for another to finish.',
    infra: 'sqs · lambda · one queue per channel, shared retry policy',
    lanes: [
      { name: 'whatsapp', detail: 'template delivered' },
      { name: 'sms', detail: 'queued with operator' },
      { name: 'email', detail: 'sent' },
      { name: 'voice', detail: 'callback scheduled' },
    ],
  },
  {
    service: 'commerce', name: 'Order and catalog updated', time: '54ms',
    description: 'Stock and order state change together, so the two cannot disagree.',
    infra: 'dynamodb transaction · eventbridge',
    results: [ { label: 'order confirmed', kind: 'ok' }, { label: 'stock −1' } ],
  },
  {
    service: 'billing', name: 'Usage metered', time: '9ms',
    description: 'What was actually sent is recorded against this account for the period.',
    infra: 'same event stream · no separate meter to reconcile',
  },
  {
    service: 'queue', name: 'A provider failed, nobody noticed', time: '1.2s',
    description: 'One carrier returned an error. The message went back on the queue and left on the next attempt.',
    infra: 'sqs redrive · exponential backoff · dead-letter queue watched',
    results: [ { label: 'attempt 2 of 5', kind: 'warn' }, { label: 'delivered', kind: 'ok' }, { label: 'dead-letter empty', kind: 'ok' } ],
  },
  {
    service: 'platform', name: 'All services healthy', time: '2.1s', complete: true,
    description: 'Every service above reported success, on the same logs, metrics and traces.',
    infra: 'cloudwatch · one dashboard for all of it',
    checks: [ 'eight services, one deployment', 'one identity, one audit trail', 'one bill' ],
  },
];

// Per-step dwell: richer steps hold longer so there is time to read them. Keyed off what
// the step contains rather than its index, so reordering STEPS does not silently retime
// the sequence.
const dwell = ( step: Step ): number => {
  if ( step.lanes ) return 1650;
  if ( step.complete ) return 1600;
  if ( step.checks ) return 1450;
  if ( step.command ) return 1400;
  return 1050;
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
        An illustration of one customer request moving through our backend: the gateway
        accepts it, the account is verified, the customer record is read, four messaging
        services run in parallel, the order and catalog update together, usage is metered,
        the queue absorbs a failed carrier attempt, and all eight services report healthy —
        every one of them on the same shared infrastructure.
      </p>

      <div className="wt-window" aria-hidden="true">
        <div className="wt-bar">
          <span className="wt-light wt-red" />
          <span className="wt-light wt-amber" />
          <span className="wt-light wt-lime" />
          <span className="wt-bar-title">platform / production</span>
          <span className="wt-bar-state"><i className="wt-state-dot" />8 services · 1 foundation</span>
        </div>

        <div className="wt-space">
          <div className="wt-request"><span className="wt-caret">›</span><span>One customer places an order. Watch what runs behind it.</span></div>

          <div ref={ streamRef }>
            { visible.map( ( step, i ) => {
              const state = i <= settled ? 'is-done' : 'is-running';
              const last = i === STEPS.length - 1;
              return (
                <div key={ step.name } className={ `wt-step ${state} ${last ? 'is-last' : ''}`.trim() }>
                  <span className="wt-dot" />
                  <div className="wt-head">
                    <span className="wt-svc">{ step.service }</span>
                    <span className={ `wt-name ${step.complete ? 'is-complete' : ''}`.trim() }>
                      { step.complete && <span className="wt-tick">✓ </span> }
                      { step.name }
                    </span>
                    <span className="wt-time">{ step.time }</span>
                  </div>
                  <p className="wt-desc">{ step.description }</p>

                  { step.command && <div className="wt-cmd">{ step.command }</div> }

                  { /* The shared foundation, written the way it would appear in code. This
                       is the line that carries the actual claim: different services,
                       same infrastructure underneath. */ }
                  { step.infra && <div className="wt-infra"># { step.infra }</div> }

                  { step.results && (
                    <div className="wt-results">
                      { step.results.map( r => (
                        <span key={ r.label } className={ `wt-chip ${r.kind ? 'is-' + r.kind : ''}`.trim() }>{ r.label }</span>
                      ) ) }
                    </div>
                  ) }

                  { /* PARALLEL LANES, side by side on purpose. Stacked vertically these
                       four would read as four more sequential steps, which is the exact
                       opposite of the point - they run at the same time. */ }
                  { step.lanes && (
                    <div className="wt-lanes">
                      { step.lanes.map( lane => (
                        <div key={ lane.name } className="wt-lane">
                          <span className="wt-lane-bar" />
                          <span className="wt-lane-name">{ lane.name }</span>
                          <span className="wt-lane-detail">{ lane.detail }</span>
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
          <span className="wt-foot-right">{ done ? '8 services · 1 retry absorbed · 1 platform' : `${shown} / ${STEPS.length} services` }</span>
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
        /* BROWN TITLE BAR, on instruction. It was #fafafa, which made the chrome the
           lightest thing in a section whose subject is a black panel - the bar drew the
           eye before the content did. A dark brown reads as a warm surround to the black
           body instead of a separate light object sitting on top of it, and it is the one
           warm value on the page so it cannot be confused with the lime accent.
           The lights had to be re-derived for it: they were dark alphas chosen for the old
           light bar, and rgba(0,0,0,.16) on brown is nearly the bar itself. Back to white
           alphas, which is correct on a dark surface. */
        .wt-bar{height:47px;flex-shrink:0;display:flex;align-items:center;gap:8px;padding:0 15px;background:#3b271a;border-bottom:1px solid rgba(209,244,112,.30)}
        .wt-light{width:11px;height:11px;border-radius:50%;flex:0 0 auto}
        /* LIME AND NEUTRALS ONLY, on instruction. The window lights were red/amber/lime
           borrowed from macOS; the first two are the only warm hues on the page and they
           pulled the eye to chrome rather than to content. Two neutral dots plus one lime
           keeps the traffic-light shape and reads as ours.
           DARK alphas, not white. The first attempt used rgba(255,255,255,.22) and .40 -
           white on a light bar. Composited against this bar's #fafafa those land on
           251,251,251 and 252,252,252: a difference of 1 and 2 out of 255, so both dots
           were invisible and the window appeared to have a single light. The panel BODY is
           black, which is what made white look right in the abstract; the title bar is
           not. Measured with a compositing check rather than judged by eye, and
           brandcheck.js now asserts each light is actually distinguishable from the bar. */
        .wt-red{background:rgba(255,255,255,.26)}
        .wt-amber{background:rgba(255,255,255,.44)}
        .wt-lime{background:#d1f470}
        .wt-bar-title{margin-left:8px;color:rgba(255,255,255,.72);font-size:13px}
        .wt-bar-state{margin-left:auto;display:flex;align-items:center;gap:7px;color:rgba(255,255,255,.58);font-size:12px}
        .wt-state-dot{width:6px;height:6px;border-radius:50%;background:#d1f470}

        /* min-height:0 is load-bearing on a flex child that scrolls: without it the
           flex item's automatic minimum size is its content, so it refuses to shrink,
           the panel grows past its 650px and nothing ever scrolls. Bottom padding is
           24px now rather than 66px - the 66 was reserving room for a footer that used
           to overlap this box and no longer does. */
        .wt-space{position:relative;flex:1;min-height:0;padding:30px 34px 24px;overflow-y:auto;overflow-x:hidden;scrollbar-width:thin;scrollbar-color:rgba(255,255,255,.24) transparent}
        .wt-space::-webkit-scrollbar{width:7px}
        .wt-space::-webkit-scrollbar-thumb{background:rgba(255,255,255,.24);border-radius:20px}

        /* EVERY SIZE IN THIS PANEL WENT UP, on instruction - the code was 10 and 11px,
           which is below what the rest of the site uses anywhere and unreadable on a
           laptop at arm's length. Monospace also runs optically smaller than Inter at the
           same nominal size, so matching the body number would still have read small.
           Floor is now 12px, with the step name and the request line at 15px. */
        .wt-request{margin-bottom:32px;display:flex;gap:10px;color:#fff;font-size:15px;line-height:1.7}
        .wt-caret{color:#d1f470}

        /* Each step fades up as it arrives. The connector is a ::before rule so it
           cannot be knocked out of alignment by content height. */
        /* LIME SEPARATORS, on instruction: the connector spine between steps, the title
           bar underline and the footer rule all carry the accent at low alpha instead of
           neutral white. Low alpha matters - at full strength a 1px lime line down the
           whole panel competes with the lime step dots that mark actual state. */
        .wt-step{position:relative;padding:0 0 29px 36px;opacity:1;transform:translateY(0);animation:wt-in .35s ease both}
        .wt-step::before{content:'';position:absolute;left:5px;top:19px;bottom:-1px;width:1px;background:rgba(209,244,112,.38)}
        .wt-step.is-last::before{display:none}
        @keyframes wt-in{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}

        .wt-dot{position:absolute;left:0;top:4px;width:12px;height:12px;z-index:2;border-radius:50%;border:2px solid rgba(255,255,255,.34);background:#000}
        /* Running is lime and pulses; settled is solid lime. The mock used blue for
           running and green for done - one accent carries both states here. */
        .wt-step.is-running .wt-dot{border-color:#d1f470;background:#d1f470;box-shadow:0 0 0 4px rgba(209,244,112,.14);animation:wt-pulse 1.2s ease-in-out infinite}
        .wt-step.is-done .wt-dot{border-color:#d1f470;background:#d1f470}
        @keyframes wt-pulse{0%,100%{opacity:.5;transform:scale(.85)}50%{opacity:1;transform:scale(1)}}

        .wt-head{min-height:20px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
        /* The service name is the new first-class thing in each row: the panel's subject
           is which service ran, not which phase of a plan it was. */
        .wt-svc{padding:2px 7px;border-radius:4px;background:rgba(209,244,112,.14);border:1px solid rgba(209,244,112,.34);color:#d1f470;font-size:11.5px;letter-spacing:.02em}
        .wt-name{color:#fff;font-size:15px;font-weight:600}
        .wt-name.is-complete{color:#d1f470}
        .wt-tick{color:#d1f470}
        .wt-time{color:rgba(255,255,255,.46);font-size:12px}
        .wt-desc{max-width:780px;margin:7px 0 0;color:rgba(255,255,255,.62);font-size:13.5px;line-height:1.65}

        .wt-cmd{margin-top:11px;padding:12px 14px;overflow-x:auto;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.14);border-radius:7px;color:#fff;font-size:13.5px;line-height:1.7;white-space:nowrap}
        .wt-sh{margin-right:7px;color:rgba(255,255,255,.46)}
        .wt-fn{color:#d1f470}
        .wt-str{color:rgba(255,255,255,.76)}
        .wt-key{color:rgba(255,255,255,.58)}
        .wt-num{color:#d1f470}
        .wt-cm{color:rgba(255,255,255,.46)}

        /* The infra comment. Dim on purpose - it is the substrate, not the event - but
           still above the 12px floor because it carries the actual message. */
        .wt-infra{margin-top:9px;color:rgba(255,255,255,.44);font-size:12.5px;line-height:1.6}

        .wt-results{margin-top:11px;display:flex;flex-wrap:wrap;gap:7px}
        .wt-chip{padding:5px 9px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.14);border-radius:5px;color:rgba(255,255,255,.62);font-size:12px}
        .wt-chip.is-ok{color:#d1f470;border-color:rgba(209,244,112,.34)}
        /* A warning is carried by weight, not by a second hue: brighter text on a
           brighter border, still neutral, so lime stays the only accent in the panel body. */
        .wt-chip.is-warn{color:rgba(255,255,255,.92);border-color:rgba(255,255,255,.38)}

        /* CONCURRENCY, SHOWN AS COLUMNS. auto-fit rather than a fixed four so the lanes
           wrap to two-by-two on a narrow panel instead of overflowing - they still read as
           simultaneous, which a horizontal scrollbar would destroy. */
        .wt-lanes{margin-top:12px;display:grid;grid-template-columns:repeat(auto-fit,minmax(132px,1fr));gap:8px}
        .wt-lane{padding:9px 10px;background:rgba(255,255,255,.04);border:1px solid rgba(209,244,112,.22);border-radius:6px;display:flex;flex-direction:column;gap:3px}
        /* A short lime rule at the top of each lane, so the four read as parallel tracks
           starting together rather than as four unrelated cards. */
        .wt-lane-bar{display:block;width:22px;height:2px;border-radius:2px;background:#d1f470;margin-bottom:3px}
        .wt-lane-name{color:#fff;font-size:12.5px;font-weight:600}
        .wt-lane-detail{color:rgba(255,255,255,.54);font-size:12px;line-height:1.45}

        .wt-checks{margin-top:11px;display:grid;gap:8px}
        .wt-check{display:flex;align-items:center;gap:8px;color:rgba(255,255,255,.62);font-size:12.5px}
        .wt-check-tick{color:#d1f470}

        /* Fades the stream out under the footer rather than letting rows collide with
           it. The gradient has to end in the panel's own #000 or it shows a seam. */
        .wt-foot{flex:0 0 auto;height:50px;padding:0 24px;display:flex;align-items:center;background:#000;border-top:1px solid rgba(209,244,112,.30);color:rgba(255,255,255,.54);font-size:12px}
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
          .wt-step.is-running .wt-dot{animation:none}
          .wt-space{scroll-behavior:auto}
        }
      `}</style>
    </section>
  );
};

export default WorkflowTerminal;
