/**
 * useConfirmDanger (Part 5) — thin wrapper over the app ConfirmContext that
 * enforces a typed-to-confirm destructive dialog for delete / unsubscribe /
 * deprecate / publish / refund / replay / access-change / secret-update.
 */
import { useConfirm } from '../../contexts/ConfirmContext';
import React from 'react';

export type DangerAction =
    | 'delete' | 'unsubscribe' | 'deprecate' | 'publish'
    | 'refund' | 'replay' | 'access-change' | 'secret-update';

const VERB: Record<DangerAction, string> = {
    delete: 'DELETE', unsubscribe: 'UNSUBSCRIBE', deprecate: 'DEPRECATE', publish: 'PUBLISH',
    refund: 'REFUND', replay: 'REPLAY', 'access-change': 'CONFIRM', 'secret-update': 'ROTATE',
};

export function useConfirmDanger () {
    const confirm = useConfirm();
    return ( action: DangerAction, message: React.ReactNode, opts?: { confirmInput?: string; title?: string } ) =>
        confirm( {
            title: opts?.title || `Confirm ${action}`,
            message,
            danger: true,
            confirmInput: opts?.confirmInput ?? VERB[ action ],
            confirmText: VERB[ action ],
        } );
}
