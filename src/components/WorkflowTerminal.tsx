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
      // ONE-SHOT, AND IT DISCONNECTS. This used to toggle `run` on every intersection
      // change, so scrolling the panel out and back in restarted the sequence from step 0 -
      // which is both a visible glitch and, together with the loop that used to follow
      // completion, the reason this panel moved without end.
      // Firing once and disconnecting is the same pattern the closing band already uses on
      // this page ("One-shot: it is an entrance, not a scroll effect"), so the two now agree.
      io = new IntersectionObserver(
        entries => {
          if ( entries.some( e => e.isIntersecting ) ) { setRun( true ); io?.disconnect(); }
        },
        { threshold: 0.25 }
      );
      io.observe( node );
    }, 0 );

    return () => { cancelled = true; window.clearTimeout( id ); if ( io ) io.disconnect(); };
  }, [] );

  // The sequence. One chained timeout rather than an interval, so a slow frame cannot
  // stack two steps on top of each other.
  //
  // IT PLAYS ONCE AND HOLDS. IT USED TO LOOP FOR EVER, AND THAT WAS TWO DEFECTS.
  //
  // On reaching the last step it waited 3200ms, then reset to `shown: 0` and started again
  // after 650ms. Measured restart-edge to restart-edge, one cycle was 15.8s - 12.6s streaming
  // and 3.2s holding - repeating for as long as the panel stayed on screen.
  //
  //   1. WCAG 2.2.2. Content that moves automatically for more than five seconds must be
  //      pausable, stoppable or hideable. This offered none of the three. Playing once is the
  //      conformant answer that needs no new control on the page, which is why it is preferred
  //      here over adding a pause button.
  //   2. THE PANEL EMPTIED ITSELF. The reset dropped it back to one 26px line inside a 551px
  //      box - 95% empty - every 15.8s. So the largest element on the home page spent part of
  //      every cycle showing nothing, and anyone arriving mid-reset met a black rectangle.
  //
  // Playing once also matches what this page already says about itself: the closing band's
  // reveal is deliberately one-shot on the stated grounds that there were already two
  // continuously moving things above it, and a third loop would compete with both. One of
  // those two was this panel. It is no longer one of them.
  //
  // THE FIRST STEP LANDS IMMEDIATELY. There was a 600ms delay before step 0, on top of the
  // observer gate, so the panel held its empty state for a measurable beat after coming into
  // view. Nothing needed that delay - the entrance animation on each step is what gives the
  // arrival its softness, and it still runs.
  useEffect( () => {
    if ( !run ) return undefined;
    let cancelled = false;
    let timer = 0;

    const step = ( index: number ) => {
      if ( cancelled ) return;
      if ( index >= STEPS.length ) {
        // Hold the finished state. No reset, no restart - see the note above.
        setDone( true );
        return;
      }
      setShown( index + 1 );
      timer = window.setTimeout( () => {
        if ( cancelled ) return;
        setSettled( index );
        timer = window.setTimeout( () => step( index + 1 ), 250 );
      }, dwell( STEPS[ index ] ) );
    };

    step( 0 );
    return () => { cancelled = true; window.clearTimeout( timer ); };
  }, [ run ] );

  // Is the reader still following the tail, or have they scrolled back to read something?
  // Starts true because the panel begins at the top with the tail in view.
  const pinnedRef = useRef( true );

  // FOLLOW THE TAIL, BUT STOP FIGHTING A READER WHO SCROLLS BACK.
  //
  // This effect used to set scrollTop = scrollHeight on every step, unconditionally. The full
  // sequence is 1350px of content in a 551px box at 1280 - and 1900px in 461px on a phone - so
  // roughly 800px scrolls past, and four of the eight steps end up above the visible edge.
  // Scrolling up to read one of them worked for at most one step: the next arrival yanked the
  // view straight back to the bottom. That is what made those steps unrecoverable rather than
  // merely off-screen, and it is the half of the defect that is fixable without cutting
  // content or growing the panel.
  //
  // WHY NOT GROW THE PANEL, which was the obvious alternative. Measured: fitting the content
  // needs 1447px at 1280 and 1997px at 390, against 650 and 560 today. On a phone that is 2.4
  // screens of black terminal, and the page goes from 2498px to about 3935px. Letting it grow
  // as steps arrive is worse again - every step would shift the rest of the page.
  //
  // So the panel keeps its height and the reader keeps control: auto-scroll only continues
  // while they are already at the bottom. 24px of tolerance, because a trackpad rarely lands
  // exactly on zero and sub-pixel rounding makes an equality test flap.
  useEffect( () => {
    const box = streamRef.current?.parentElement;
    if ( !box ) return undefined;
    const onScroll = () => {
      pinnedRef.current = box.scrollHeight - box.scrollTop - box.clientHeight < 24;
    };
    box.addEventListener( 'scroll', onScroll, { passive: true } );
    return () => box.removeEventListener( 'scroll', onScroll );
  }, [] );

  // Inside the panel only - this must never scroll the page.
  useEffect( () => {
    const box = streamRef.current?.parentElement;
    if ( !box || !pinnedRef.current ) return;
    box.scrollTop = box.scrollHeight;
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

      {/* dir="ltr" LOCKS THE TERMINAL, and it is a correctness fix rather than a preference.
          This panel draws literal machine output - a shell prompt, "platform / production",
          $contacts.get("cust_2841"), "# dynamodb · single-table". None of that is prose and
          none of it is left-to-right by convention: it is left-to-right by SYNTAX. With the
          document mirrored for an Arabic reader the flex rows inside reversed, so the window
          lights moved to the right, the prompt reversed, and the punctuation in the call
          reordered - a reader who knows the API would see code that no longer parses.
          Found by measuring mirror symmetry, not by looking: comparing each element's
          distance from the inline-start edge in ltr against rtl, this subtree was the largest
          asymmetry on the home page at 726px.
          It pairs with the aria-hidden already here. Both say the same thing about this
          panel - it is a picture of a machine, not text - so it is exempt from translation
          and from mirroring for one reason. */}
      <div className="wt-window" aria-hidden="true" dir="ltr">
        <div className="wt-bar">
          {/* Class names carry the POSITION, not the colour. They were wt-red / wt-amber /
              wt-lime and each one outlived the colour it named at least once - see the rule
              block. A name that lies about its value is worse than a generic one. */}
          <span className="wt-light wt-light-1" />
          <span className="wt-light wt-light-2" />
          <span className="wt-light wt-light-3" />
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
        /* THREE COLOURS AGAIN, AND THIS REVERSES THE EARLIER INSTRUCTION ON PURPOSE.
           Owner picked option 3B from docs/accent-review after seeing the alternatives. The
           note above records why they were neutralised - warm hues on chrome pulling the eye
           away from content - and that reasoning is not wrong, it is now outweighed. Keeping
           the old note rather than deleting it, because a reversal is only informative if what
           it reversed is still readable.

           MEASURED ON THIS BAR (#3b271a), not on white, because the composited background is
           what decides legibility:

             #f0a818 amber    6.92:1
             #9849e8 purple   2.99:1
             #3da35a green    4.42:1
             previous neutrals .26 / .44 -> 2.30:1 and 3.97:1

           PURPLE IS BELOW 3:1 AND THAT IS ACCEPTED HERE, deliberately and with the reason
           written down. A WCAG ratio measures LUMINANCE ONLY; saturated purple against dark
           brown differs strongly in hue and chroma, which the metric does not count, and the
           rendered frame is plainly legible - I checked the picture after writing the number,
           having first told the owner it "sits almost on top of" the bar, which was wrong.
           1.4.11 does not apply regardless: this whole window is aria-hidden decorative chrome
           and carries no state. The two neutrals it replaces were 2.30:1, so this is an
           improvement on what shipped rather than a concession.

           STILL NO ANIMATION. 3C offered a pulse and was not chosen; a permanently breathing
           light in the corner is the WCAG 2.2.2 problem that already removed this panel's
           terminal loop. */
        .wt-light-1{background:#f0a818}
        .wt-light-2{background:#9849e8}
        .wt-light-3{background:#3da35a}
        .wt-bar-title{margin-left:8px;color:rgba(255,255,255,.72);font-size:13px}
        .wt-bar-state{margin-left:auto;display:flex;align-items:center;gap:7px;color:rgba(255,255,255,.58);font-size:12px}
        /* GREEN, NOT LIME, and only this dot changes - see the note below on the two that
           deliberately do not.
           This sits in the same 47px strip as the three window lights, beside the copy
           "8 services · 1 foundation". Once those lights became amber/purple/green it was the
           only lime left in a bar that no longer uses lime, which read as a leftover rather
           than as a colour anyone chose.
           #3da35a is the third light's own value, so no new colour enters the file, and green
           for "8 services healthy" is the one hue here that already means what the sentence
           says. Measured on this bar's #3b271a: 4.42:1, down from lime's 11.32:1. That drop is
           the cost and it is well clear of 3:1 on a 6px decorative dot inside an aria-hidden
           window. */
        .wt-state-dot{width:6px;height:6px;border-radius:50%;background:#3da35a}

        /* min-height:0 is load-bearing on a flex child that scrolls: without it the
           flex item's automatic minimum size is its content, so it refuses to shrink,
           the panel grows past its 650px and nothing ever scrolls. Bottom padding is
           24px now rather than 66px - the 66 was reserving room for a footer that used
           to overlap this box and no longer does. */
        /* THE SCROLLBAR IS VISIBLE, AND THAT IS PART OF THE SAME FIX.
           The thumb was rgba(255,255,255,.24) on a transparent track, over a #000 panel - so
           the channel was invisible and the thumb was close to it. About 800px of the sequence
           scrolls past at 1280 and 1439px on a phone, and nothing indicated that there was
           anything above the visible edge to go back to. Overflow the reader cannot see is
           overflow they will not look for.
           .38 thumb on a .08 track: the track is what makes the region legible as scrollable
           at rest, which the thumb alone does not do. Both are white alphas on the existing
           panel, so no new colour enters. */
        .wt-space{position:relative;flex:1;min-height:0;padding:30px 34px 24px;overflow-y:auto;overflow-x:hidden;scrollbar-width:thin;scrollbar-color:rgba(255,255,255,.38) rgba(255,255,255,.08)}
        .wt-space::-webkit-scrollbar{width:7px}
        .wt-space::-webkit-scrollbar-track{background:rgba(255,255,255,.08);border-radius:20px}
        .wt-space::-webkit-scrollbar-thumb{background:rgba(255,255,255,.38);border-radius:20px}

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

        /* ONE HUE PER SERVICE, and this is a system rather than decoration - which is the
           difference that makes it defensible here after the window lights took three colours.
           Each step IS a named service (gateway, auth, contacts, messaging, commerce, billing,
           queue, platform), so a hue that identifies the service is the same use the rotating
           hero pill puts this palette to: one colour per subject.

           STATE IS STILL NOT CARRIED BY HUE, which is the constraint that had to hold. Before
           this, lime meant "ran", so the hue was doing two jobs at once. What separates the two
           states now:
             running   pulsing
             done      static
           plus .wt-name.is-complete turns the service name lime, the row carries a tick, and
           the footer reads "running" / "complete" in words. Three non-colour signals, so WCAG
           1.4.1 is not engaged: hue says WHICH service, motion and text say WHETHER it ran.

           The hollow .wt-dot default above is a fallback that NO rendered step uses - the
           component assigns every visible step either is-done or is-running
           (state = i <= settled ? 'is-done' : 'is-running'), so there is no pending dot on
           screen to distinguish. Worth stating because "pending is hollow" is the obvious thing
           to assume from reading the CSS alone, and it would be wrong.

           MEASURED ON THE PANEL BODY #000, every value already in this repo:
             lime   #d1f470  16.89:1    amber #f0a818  10.32:1
             green  #3da35a   6.58:1    purple #9849e8  4.45:1
             blue   #2563eb   4.06:1    red    #dc2626  4.35:1

           RED IS EXCLUDED DELIBERATELY, and it is the only one that clears contrast and is
           still wrong. Step 7 reads "A provider failed, nobody noticed" - the whole point of
           that line is that the failure was absorbed - and step 6 is "Usage metered". A red dot
           on either reads as an alarm about the thing being described. Five hues cycle instead,
           ordered so no two adjacent steps repeat, and step 8 "All services healthy" lands on
           green because that is the one hue whose convention matches its sentence. */
        /* THREE PROPERTIES PER STEP, FROM ONE SOURCE OF TRUTH.
           --rgb   the hue as bare channels, so a tint can be mixed with rgba() without a
                   second literal to keep in sync. There is no color-mix() anywhere in this
                   repo and no browserslist declaring support for it, so rgba(var(--rgb),a)
                   is the portable way to get "this hue at 14%" - it works wherever custom
                   properties do, which is everywhere this site is served.
           --dot   the solid hue, derived. Substitution happens before the value is parsed,
                   so rgb(var(--rgb)) resolves to rgb(37,99,235) and every existing
                   var(--dot) usage keeps working untouched.
           --ink   the same hue LIFTED until it is legible as text. Defaults to --dot and is
                   overridden only where it has to be - see the note on --ink below.

           Deriving --dot rather than listing both is deliberate: a hex and a channel triple
           for the same colour is two things to edit and one to forget. */
        .wt-step{--rgb:209,244,112;--dot:rgb(var(--rgb));--ink:var(--dot)}
        /* --ink EXISTS BECAUSE TWO OF THE FIVE HUES ARE NOT LEGIBLE AS TEXT ON #000, and the
           comment this replaces got that wrong in writing. It said the lowest of the five was
           "blue at 4.06:1. Well clear of 4.5:1 for 15px/600 text". 4.06 is not clear of 4.5,
           it is BELOW it - so the rule as shipped was a latent AA failure waiting for a data
           change: mark step 1 or 6 complete and its name renders blue at 4.06:1. Nothing was
           visibly broken only because step 8, the single complete step, happens to be green.
           Purple was the same story with less margin to spare, at 4.45:1.

           The lift is the smallest that clears 4.5:1 on the pill's own tinted background:
             blue    #2563eb -> #3d74ed   4.51:1   11% toward white
             purple  #9849e8 -> #9f56ea   4.56:1    7% toward white
             amber, lime, green unchanged - they already clear it at 8.60, 13.10 and 5.78:1
           11% and 7% are small enough that the dot and its pill read as the same colour: blue
           moves 43 of a possible 765 in RGB distance. And the five inks stay distinguishable
           from each other - the closest pair, blue and purple, is 131 apart. */
        .wt-step:nth-child(1){--rgb:37,99,235;--ink:#3d74ed}
        .wt-step:nth-child(2){--rgb:152,73,232;--ink:#9f56ea}
        .wt-step:nth-child(3){--rgb:240,168,24}
        .wt-step:nth-child(4){--rgb:209,244,112}
        .wt-step:nth-child(5){--rgb:61,163,90}
        .wt-step:nth-child(6){--rgb:37,99,235;--ink:#3d74ed}
        .wt-step:nth-child(7){--rgb:240,168,24}
        .wt-step:nth-child(8){--rgb:61,163,90}

        /* Running fills and pulses; done fills. The glow is NEUTRAL white at .10 rather than
           the lime rgba(209,244,112,.14) it was: a lime halo around a blue or purple dot reads
           as two colours fighting, and a per-hue halo would need a second variable for every
           step to say the same thing a neutral one says once. */
        .wt-step.is-running .wt-dot{border-color:var(--dot);background:var(--dot);box-shadow:0 0 0 4px rgba(255,255,255,.10);animation:wt-pulse 1.2s ease-in-out infinite}
        .wt-step.is-done .wt-dot{border-color:var(--dot);background:var(--dot)}
        @keyframes wt-pulse{0%,100%{opacity:.5;transform:scale(.85)}50%{opacity:1;transform:scale(1)}}

        .wt-head{min-height:20px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
        /* The service name is the new first-class thing in each row: the panel's subject
           is which service ran, not which phase of a plan it was.

           THE PILL NOW CARRIES ITS SERVICE'S OWN HUE, and this reverses an earlier call.
           It was lime on all eight, with the reasoning that "giving it five colours would
           turn a label into a legend the reader is expected to decode". Owner overruled it,
           three times, and on reflection the objection was answering the wrong question.
           This pill contains the service's own name - gateway, auth, contacts - so it IS the
           service identity, which is precisely what the dot hue encodes. Lime on all eight meant the
           one element naming the service was the one element refusing to colour it, and lime
           there had stopped meaning anything at all: it was the last survivor of the old
           "lime = ran" scheme that the per-service dots replaced.

           Nothing is asked of the reader that was not already asked. The hue is not a legend
           to decode because the pill spells the service out in words beside it; colour is
           redundant reinforcement of text that is already there, which is the one use of
           colour that costs a reader nothing.

           WHY THE BACKGROUND TINTS TOO. A blue ink on the old lime-tinted chip is two hues
           fighting in a 40px box - measured, blue ink on #1d2210 is 3.15:1 and fails outright.
           Tinting bg and border from the same --rgb puts the ink on its own hue's near-black
           ground (#050e21 for blue) where it clears 4.5:1. Same alphas as before, .14 and .34,
           so the chip's weight on the panel is unchanged. */
        .wt-svc{padding:2px 7px;border-radius:4px;background:rgba(var(--rgb),.14);border:1px solid rgba(var(--rgb),.34);color:var(--ink);font-size:11.5px;letter-spacing:.02em}
        .wt-name{color:#fff;font-size:15px;font-weight:600}
        /* THE COMPLETED NAME AND ITS TICK TAKE THE STEP'S OWN HUE, not lime.
           Both were #d1f470 while the dots were lime too, so the row agreed with itself. Once the
           dots became one hue per service, lime here was the last thing in the panel still
           claiming the old meaning - and measured, only ONE row was affected: names are #fff on
           steps 1-7 and lime only on step 8, the is-complete one. So "the text is still lime" was
           three separate things - this name, this tick, and the .wt-svc pill.

           THE PILL IS NOW IN THE SAME SCHEME - see the note on .wt-svc. It used to be excluded
           and held lime on all eight, which meant this rule recoloured exactly ONE line in the
           whole panel (step 8, the only step whose data says complete:true) while the eight
           pills stayed lime. That is why the change was reported as "not showing" after it
           shipped correct: it was a single row moving from lime to green, two greens, against
           eight unchanged lime chips.

           USES --ink, NOT --dot, and that is the fix for a latent AA failure rather than a
           preference. This rule paints 15px/600 text, which needs 4.5:1. Raw blue is 4.06:1 on
           #000 and raw purple 4.45:1, so marking step 1 or 6 complete would have shipped
           failing text - see the note beside --ink. --ink is the same hue lifted just past the
           floor, and it is identity for amber, lime and green, so step 8 is pixel-identical to
           what it renders today.

           COST, STATED: a completed name goes from white at 21:1 to its own hue, lowest 4.51:1.
           A real reduction on the panel's primary text, worth knowing rather than discovering.
           State is not carried by this colour either way - the pulse, the tick glyph and the
           footer's "running"/"complete" wording do that, so WCAG 1.4.1 stays unengaged. */
        .wt-name.is-complete,.wt-tick{color:var(--ink)}
        /* .46 IS 4.58:1 ON THIS PANEL - eight hundredths above the 4.5:1 floor for text this
           size, and the tightest margin anywhere on the home page. Left alone deliberately,
           and the reason is the rung below it: .wt-infra was raised from .44 to .50 when it
           failed, and a timestamp has to stay dimmer than the infrastructure line or the two
           read as equals. Moving this to .50 would collapse that distinction to fix a value
           that already passes. What it must not do is drift DOWN: .45 is 4.47:1 and fails, so
           there is no headroom here at all. flowprobe.js asserts the measured ratio, which is
           why a one-notch nudge cannot land quietly. */
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
           still above the 12px floor because it carries the actual message.
           .50, NOT .44, AND THE REASON IS MEASURED. This line is the one that makes the
           section's argument - "# dynamodb · single-table · on-demand capacity", the shared
           foundation named under every step - and at rgba(255,255,255,.44) it composited to
           4.25:1 on #000, below the 4.5:1 WCAG 1.4.3 requires at 12.5px/400. It was the only
           one of the fourteen text styles in this panel that failed; .50 measures 5.28:1.
           Deliberately NOT .62: that is .wt-desc's value, and this line must stay dimmer than
           the description it sits under, which is the whole point of the "dim on purpose"
           above. .50 is the smallest step that clears AA and keeps that order intact.
           NOTE .wt-cm above passes at 4.58:1, i.e. by 0.08 - any further dimming of it fails.
           Re-measure with: node tools/browser/flowprobe.js - it asserts every ratio here.
           (No backticks in this comment: this sits inside a style jsx template literal, where
           one stray backtick ends the literal and the build fails at type-check.) */
        .wt-infra{margin-top:9px;color:rgba(255,255,255,.50);font-size:12.5px;line-height:1.6}

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
        /* STAYS LIME, DELIBERATELY, and this is the boundary of the recolour.
           This dot sits beside "running" / "complete" on the BLACK footer, not the brown title
           bar, and it reports live state - it is the same claim the lime .wt-dot step markers
           make inside the panel, where lime means "this service ran". The title-bar lights are
           decorative chrome and could take any hue; these two are the panel's only actual
           signal, and recolouring them would spend the accent on decoration and leave the
           meaning without a colour of its own. Lime on #000 is 11.90:1 here.
           If the owner wants this one moved too it is one line - but it should be moved knowing
           it takes the step dots with it, or the footer and the steps stop agreeing. */
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
