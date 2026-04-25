// Velo SEO code — add to each page's code panel
// This clears any runtime SEO and sets fresh values
import wixSeoFrontend from 'wix-seo-frontend';

$w.onReady(() => {
  // Clear existing SEO (set to empty/defaults)
  wixSeoFrontend.setTitle('');
  wixSeoFrontend.setMetaTags([]);
  wixSeoFrontend.setLinks([]);
  wixSeoFrontend.setStructuredData([]);
});
