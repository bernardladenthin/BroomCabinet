// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

// Presses the download button on an Outlook attachment preview. Open one of the deep links
// `pymstodoexport.py links` prints (https://outlook.live.com/mail/0/deeplink/attachment/...),
// then run this in the console of that tab. Waits up to 20 s for the preview to appear.
//
// THE BROWSER MUST BE ALLOWED TO DOWNLOAD SEVERAL FILES from outlook.live.com: Chrome silently
// blocks every download after the first one from the same page until that is granted (the icon
// at the right of the address bar). Nothing fails visibly -- the files just never arrive.
//
// The button is found by its label, in the UI languages listed here; add yours if it is missing.
(async () => {
  const labels = ['Herunterladen', 'Download'];
  const t0 = Date.now();
  let button;
  while (Date.now() - t0 < 20000) {
    button = [...document.querySelectorAll('button')]
      .find(b => labels.includes((b.getAttribute('aria-label') || b.textContent || '').trim()));
    if (button) break;
    await new Promise(r => setTimeout(r, 300));
  }
  if (!button) throw new Error('no download button found (labels tried: ' + labels.join(', ') + ')');
  button.click();
  console.log('download started');
})();
