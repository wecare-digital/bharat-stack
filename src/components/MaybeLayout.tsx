/**
 * MaybeLayout — renders the full app Layout (sidebar/header/breadcrumbs) for a
 * standalone page, OR just the children when `embedded` (e.g. inside a PageShell
 * tab hub). Lets a page work both as its own route AND embedded, without
 * double-wrapping the Layout.
 *
 * Usage: replace `<Layout user={user} onSignOut={signOut}>` with
 *        `<MaybeLayout embedded={embedded} user={user} onSignOut={signOut}>`
 *        and `</Layout>` with `</MaybeLayout>`.
 */
import React from 'react';
import Layout from './Layout';

interface MaybeLayoutProps {
    embedded?: boolean;
    user?: any;
    onSignOut?: () => void;
    children: React.ReactNode;
}

const MaybeLayout: React.FC<MaybeLayoutProps> = ( { embedded = false, user, onSignOut, children } ) => {
    if ( embedded ) return <>{ children }</>;
    return (
        <Layout user={ user } onSignOut={ onSignOut }>
            { children }
        </Layout>
    );
};

export default MaybeLayout;
