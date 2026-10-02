import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const SOURCE = fs.readFileSync( path.join( process.cwd(), 'src/pages/404.tsx' ), 'utf8' );

describe( 'missing pages use one home fallback', () => {
  it( 'uses a literal home destination without legacy exceptions', () => {
    expect( SOURCE ).toMatch( /router\.replace\(\s*'\/'\s*\)/ );
    expect( SOURCE ).not.toMatch( /router\.push|window\.location|RETIRED_PATH_PREFIXES/ );
  } );
  it( 'is not indexed', () => {
    expect( SOURCE ).toContain( '<meta name="robots" content="noindex, follow" />' );
  } );
  it( 'provides an explicit home link', () => {
    expect( SOURCE ).toMatch( /<a[^>]*href="\/"/ );
    expect( SOURCE ).toContain( 'This page is unavailable.' );
  } );
} );
