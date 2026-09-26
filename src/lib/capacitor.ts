/**
 * Capacitor Native Integration - WECARE.DIGITAL
 *
 * Initializes all native plugins (push, splash, status bar, haptics,
 * deep links, keyboard) when running inside a Capacitor shell.
 * Safe no-op on web.
 */

import { Capacitor } from '@capacitor/core';
import { App, type URLOpenListenerEvent } from '@capacitor/app';
import { SplashScreen } from '@capacitor/splash-screen';
import { StatusBar, Style } from '@capacitor/status-bar';
import { PushNotifications } from '@capacitor/push-notifications';
import { Browser } from '@capacitor/browser';
import { Haptics, ImpactStyle } from '@capacitor/haptics';
import { Keyboard } from '@capacitor/keyboard';

/* ── Helpers ── */
export const isNative = () => Capacitor.isNativePlatform();
export const isIOS = () => Capacitor.getPlatform() === 'ios';
export const isAndroid = () => Capacitor.getPlatform() === 'android';

/* ── Push Notifications ── */
export async function initPushNotifications(
  onToken: (token: string) => void,
  onNotification: (data: any) => void,
) {
  if (!isNative()) return;

  const perm = await PushNotifications.requestPermissions();
  if (perm.receive !== 'granted') return;

  await PushNotifications.register();

  PushNotifications.addListener('registration', (token) => {
    console.log('[Push] Token:', token.value);
    onToken(token.value);
  });

  PushNotifications.addListener('registrationError', (err) => {
    console.error('[Push] Registration error:', err);
  });

  PushNotifications.addListener('pushNotificationReceived', (notification) => {
    console.log('[Push] Received:', notification);
    onNotification(notification);
  });

  PushNotifications.addListener('pushNotificationActionPerformed', (action) => {
    console.log('[Push] Action:', action);
    onNotification(action.notification);
  });
}

/* ── Status Bar ── */
export async function configureStatusBar(dark = true) {
  if (!isNative()) return;
  await StatusBar.setStyle({ style: dark ? Style.Dark : Style.Light });
  if (isAndroid()) {
    await StatusBar.setBackgroundColor({ color: '#1a3a2a' });
  }
}

/* ── Splash Screen ── */
export async function hideSplash() {
  if (!isNative()) return;
  await SplashScreen.hide({ fadeOutDuration: 300 });
}

/* ── Haptics ── */
export async function hapticTap() {
  if (!isNative()) return;
  await Haptics.impact({ style: ImpactStyle.Light });
}

export async function hapticSuccess() {
  if (!isNative()) return;
  await Haptics.notification({ type: 'SUCCESS' as any });
}

export async function hapticError() {
  if (!isNative()) return;
  await Haptics.notification({ type: 'ERROR' as any });
}

/* ── External Browser ── */
export async function openExternal(url: string) {
  if (isNative()) {
    await Browser.open({ url, presentationStyle: 'popover' });
  } else {
    window.open(url, '_blank', 'noopener');
  }
}

/* ── Deep Links ── */
export function initDeepLinks(navigate: (path: string) => void) {
  if (!isNative()) return;

  App.addListener('appUrlOpen', (event: URLOpenListenerEvent) => {
    // Handle wecare:// scheme and universal links. Rewritten onto the apex, which is
    // the host Amplify serves; stack.wecare.digital was retired and only 301'd here.
    let url: URL;
    try {
      url = new URL(event.url
        .replace('wecare://', 'https://wecare.digital/')
      );
    } catch {
      return;
    }
    // Short links — let the redirect Lambda resolve the code.
    //
    // TWO forms, both live and both required:
    //   wecare.digital/r/<code>   canonical since 2026-09-26, what we mint now
    //   r.wecare.digital/<code>   every link issued before that
    //
    // The subdomain branch is not legacy cruft to be cleaned up later. Short links
    // are printed on physical materials and embedded in messages already delivered
    // (see PROTECTED_TABLES in operations/system-cleanup), so a handset opening the
    // old form has to keep working for as long as those exist. Dropping this branch
    // would make the app swallow its own short links while a browser still followed
    // them, which is the worst failure shape: broken only for the people who
    // installed the app.
    const isApexShortLink =
      (url.hostname === 'wecare.digital' || url.hostname === 'www.wecare.digital')
      && /^\/r\/.+/.test(url.pathname);

    if (url.hostname === 'r.wecare.digital' || isApexShortLink) {
      const code = isApexShortLink
        ? url.pathname.replace(/^\/r\//, '')
        : url.pathname.replace(/^\//, '');
      if (code) navigate(`/link?opened=${code}`);
      return;
    }
    const path = url.pathname;
    if (path) navigate(path);
  });
}

/* ── Back Button (Android) ── */
export function initBackButton(goBack: () => void) {
  if (!isAndroid()) return;

  App.addListener('backButton', ({ canGoBack }) => {
    if (canGoBack) {
      goBack();
    } else {
      App.exitApp();
    }
  });
}

/* ── Keyboard ── */
export function initKeyboard(
  onShow?: (height: number) => void,
  onHide?: () => void,
) {
  if (!isNative()) return;

  Keyboard.addListener('keyboardWillShow', (info) => {
    onShow?.(info.keyboardHeight);
  });

  Keyboard.addListener('keyboardWillHide', () => {
    onHide?.();
  });
}

/* ── Master Init ── */
export async function initCapacitor(router: { push: (path: string) => void; back: () => void }) {
  if (!isNative()) return;

  await configureStatusBar(true);
  await hideSplash();
  initDeepLinks((path) => router.push(path));
  initBackButton(() => router.back());
  initKeyboard();
}
