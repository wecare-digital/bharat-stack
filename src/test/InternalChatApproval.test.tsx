/**
 * The approval panel in the internal chat, and the one thing it must never imply.
 *
 * Context: `governance.py` refuses all 18 APPLY tools, and until now a refusal never
 * reached the browser at all — the loop fed it back to the model and only the
 * model's prose came out, so an operator saw a narration of what the agent wanted to
 * do and had nothing concrete to act on.
 *
 * The panel closes that gap, and in doing so creates a new way to be wrong: a green
 * tick next to "Approve" that reads as "sent". Approving records a decision; every
 * APPLY is still disabled, so applying still refuses. These tests pin that, plus the
 * two properties that make approval-by-hash safe:
 *
 *   - only `planHash` leaves the browser, so a client cannot display one intent and
 *     approve another
 *   - the approver is never read from anything client-side
 */
import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import fs from 'node:fs';
import path from 'node:path';

vi.mock( 'aws-amplify/auth', () => ( {
  fetchAuthSession: vi.fn().mockResolvedValue( {
    tokens: { accessToken: { toString: () => 'test-token' } },
  } ),
} ) );

import InternalChatTab from '../components/dashboard/tabs/InternalChatTab';

const SRC = fs.readFileSync(
  path.resolve( __dirname, '../components/dashboard/tabs/InternalChatTab.tsx' ),
  'utf8' );

// What `describe_plan` actually returns: recipient masked to four digits, message
// body omitted. The browser never holds the real values.
const PLAN = {
  tool: 'send_whatsapp',
  toolClass: 'APPLY',
  catalogVersion: '2',
  planHash: 'a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90',
  idempotencyKey: 'send_whatsapp#a1b2c3d4',
  createdAt: 1_800_000_000,
  arguments: { to: '...0044', content: '<omitted 24 chars>' },
  summary: 'Send a WhatsApp text message',
  wouldApply: false,
  refusal: 'refused until the plan/approval/receipt path exists',
};

function generateResponse( plans: unknown[] ) {
  return {
    ok: true,
    status: 200,
    json: async () => ( {
      suggestedResponse: 'I was not able to send that. Ask an operator to approve it.',
      sessionId: 'dash-test',
      pendingPlans: plans,
    } ),
  };
}

function approvalResponse( body: Record<string, unknown>, status = 200 ) {
  return { ok: status < 400, status, json: async () => body };
}

async function askSomething() {
  fireEvent.change( screen.getByPlaceholderText( /Type a command/i ),
    { target: { value: 'message the customer' } } );
  fireEvent.click( screen.getByRole( 'button', { name: /^Send$/ } ) );
}

let calls: Array<{ url: string; init: RequestInit }>;

beforeEach( () => {
  calls = [];
  // jsdom has no scrollIntoView, and the chat scrolls to the bottom on every
  // message. Not the behaviour under test.
  if ( !( 'scrollIntoView' in Element.prototype ) ) {
    ( Element.prototype as any ).scrollIntoView = () => {};
  }
} );

afterEach( () => {
  vi.unstubAllGlobals();
} );

function stubFetch( handler: ( url: string, init: RequestInit ) => any ) {
  vi.stubGlobal( 'fetch', vi.fn( ( url: string, init: RequestInit ) => {
    calls.push( { url: String( url ), init } );
    return Promise.resolve( handler( String( url ), init ) );
  } ) );
}

describe( 'the withheld-action panel', () => {
  it( 'appears when the agent was refused, and says approving does not send', async () => {
    stubFetch( () => generateResponse( [ PLAN ] ) );
    render( <InternalChatTab /> );
    await askSomething();

    await waitFor( () => expect( screen.getByText( /One action was withheld/i ) ).toBeTruthy() );
    // The load-bearing sentence. Without it a person clicks Approve and believes a
    // customer was messaged.
    expect( screen.getByText( /It does not\s+send anything/i ) ).toBeTruthy();
    expect( screen.getByText( 'send_whatsapp' ) ).toBeTruthy();
  } );

  it( 'is absent when nothing was refused', async () => {
    stubFetch( () => generateResponse( [] ) );
    render( <InternalChatTab /> );
    await askSomething();

    await waitFor( () => expect( screen.queryByText( /withheld/i ) ).toBeNull() );
    expect( screen.queryByRole( 'button', { name: /Approve/ } ) ).toBeNull();
  } );

  it( 'shows the masked recipient it was given and never a full number', async () => {
    stubFetch( () => generateResponse( [ PLAN ] ) );
    render( <InternalChatTab /> );
    await askSomething();

    await waitFor( () => expect( screen.getByText( /to: \.\.\.0044/ ) ).toBeTruthy() );
    expect( document.body.textContent ).not.toMatch( /\+?91\d{10}/ );
  } );

  it( 'drops a plan with no planHash rather than offering an Approve that cannot work',
    async () => {
      stubFetch( () => generateResponse( [ { ...PLAN, planHash: undefined } ] ) );
      render( <InternalChatTab /> );
      await askSomething();

      await waitFor( () => expect( screen.queryByText( /withheld/i ) ).toBeNull() );
    } );
} );

describe( 'approving', () => {
  it( 'sends only the plan hash — never the tool or the arguments', async () => {
    stubFetch( ( url ) => url.includes( '/ai/approvals' )
      ? approvalResponse( {
        success: true, approved: true, stillDisabled: true,
        approval: { planHash: PLAN.planHash, approvedBy: 'manish@wecare.digital',
          expiresAt: 1_800_000_900, consumed: false },
        plan: PLAN,
        nextStep: 'Nothing has been sent.',
      } )
      : generateResponse( [ PLAN ] ) );

    render( <InternalChatTab /> );
    await askSomething();
    await waitFor( () => screen.getByRole( 'button', { name: /Approve/ } ) );
    fireEvent.click( screen.getByRole( 'button', { name: /Approve/ } ) );

    await waitFor( () => expect( calls.some( c => c.url.includes( '/ai/approvals' ) ) ).toBe( true ) );
    const approve = calls.find( c => c.url.includes( '/ai/approvals' ) )!;
    const body = JSON.parse( String( approve.init.body ) );

    expect( body.planHash ).toBe( PLAN.planHash );
    // A client that supplied its own arguments could show one recipient and approve
    // another. The server holds the draft; the client refers to it.
    expect( body ).not.toHaveProperty( 'arguments' );
    expect( body ).not.toHaveProperty( 'tool' );
    // The approver comes from the bearer token, so naming one here would be a way
    // around `_normalise_approver`.
    expect( body ).not.toHaveProperty( 'approvedBy' );
    expect( Object.keys( body ).sort() ).toEqual( [ 'catalogVersion', 'planHash' ] );
  } );

  it( 'reports the approval as recorded and still not sent', async () => {
    stubFetch( ( url ) => url.includes( '/ai/approvals' )
      ? approvalResponse( {
        success: true, approved: true, stillDisabled: true,
        approval: { planHash: PLAN.planHash, approvedBy: 'manish@wecare.digital',
          expiresAt: 1_800_000_900, consumed: false },
      } )
      : generateResponse( [ PLAN ] ) );

    render( <InternalChatTab /> );
    await askSomething();
    await waitFor( () => screen.getByRole( 'button', { name: /Approve/ } ) );
    fireEvent.click( screen.getByRole( 'button', { name: /Approve/ } ) );

    await waitFor( () => expect( screen.getByText( 'Approved' ) ).toBeTruthy() );
    expect( screen.getByText( /nothing was sent/i ) ).toBeTruthy();
    expect( screen.getByText( /Single use/i ) ).toBeTruthy();
    expect( screen.getByText( /manish@wecare\.digital/ ) ).toBeTruthy();
  } );

  it( 'surfaces a 403 as an Admin requirement, not a generic failure', async () => {
    stubFetch( ( url ) => url.includes( '/ai/approvals' )
      ? approvalResponse( {
        error: 'MFA required',
        detail: 'Administrator actions require a second factor.',
      }, 403 )
      : generateResponse( [ PLAN ] ) );

    render( <InternalChatTab /> );
    await askSomething();
    await waitFor( () => screen.getByRole( 'button', { name: /Approve/ } ) );
    fireEvent.click( screen.getByRole( 'button', { name: /Approve/ } ) );

    await waitFor( () => expect(
      screen.getByText( /second factor/i ) ).toBeTruthy() );
    // Not approved, so the button must still be a button.
    expect( screen.queryByText( 'Approved' ) ).toBeNull();
  } );

  it( 'shows the server refusal verbatim when the approval is rejected', async () => {
    stubFetch( ( url ) => url.includes( '/ai/approvals' )
      ? approvalResponse( {
        success: false, refused: true,
        reason: 'no drafted plan with that hash.',
        planHash: PLAN.planHash,
      } )
      : generateResponse( [ PLAN ] ) );

    render( <InternalChatTab /> );
    await askSomething();
    await waitFor( () => screen.getByRole( 'button', { name: /Approve/ } ) );
    fireEvent.click( screen.getByRole( 'button', { name: /Approve/ } ) );

    await waitFor( () => expect(
      screen.getByText( /no drafted plan with that hash/i ) ).toBeTruthy() );
  } );

  it( 'reports a network failure as nothing approved', async () => {
    stubFetch( ( url ) => {
      if ( url.includes( '/ai/approvals' ) ) throw new Error( 'offline' );
      return generateResponse( [ PLAN ] );
    } );

    render( <InternalChatTab /> );
    await askSomething();
    await waitFor( () => screen.getByRole( 'button', { name: /Approve/ } ) );
    fireEvent.click( screen.getByRole( 'button', { name: /Approve/ } ) );

    await waitFor( () => expect(
      screen.getByText( /Nothing was approved/i ) ).toBeTruthy() );
  } );
} );

describe( 'the source keeps the properties that make this safe', () => {
  it( 'trusts the server for stillDisabled rather than hardcoding it', () => {
    // If this were hardcoded true, the panel would keep claiming "nothing was sent"
    // on the day an APPLY is enabled — which is the exact class of confidently wrong
    // UI this whole phase has been removing.
    expect( SRC ).toContain( 'data.stillDisabled !== false' );
  } );

  it( 'clears last turn\'s plans instead of accumulating them', () => {
    // An Approve button left attached to a request the operator has moved on from is
    // an approval waiting to be given for the wrong thing.
    expect( SRC ).toContain( 'setApprovalState({})' );
  } );

  it( 'does not paint the withheld surface in the success green', () => {
    // #1a3a2a is the dashboard's own green and reads as "fine". A withheld action is
    // neither fine nor broken, so the panel is amber.
    const panel = SRC.slice( SRC.indexOf( 'actions were withheld' ) - 1200,
      SRC.indexOf( 'actions were withheld' ) );
    expect( panel ).toContain( '#b45309' );
  } );
} );
