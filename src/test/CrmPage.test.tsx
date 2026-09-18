import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

describe( 'legacy CRM public route', () => {
  it( 'is deleted from the public page tree', () => {
    expect( existsSync( resolve( process.cwd(), 'src/pages/crm/index.tsx' ) ) ).toBe( false );
  } );
} );
