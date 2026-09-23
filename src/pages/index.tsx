import React from 'react';
import Head from 'next/head';
import BrandBadge from '../components/BrandBadge';

const HomePage: React.FC = () => (
  <>
    <Head>
      <title>Bharat Stack by WECARE.DIGITAL</title>
      <meta name="description" content="Bharat Stack by WECARE.DIGITAL." />
      <link rel="canonical" href="https://wecare.digital/" />
    </Head>
    <main className="home-shell" aria-label="Bharat Stack home">
      {/* Same pill as the Grahak OS hero, with the maker line flipped: this page is
          the company, that page is one product of it. Sits inside .home-layout so
          it inherits the canvas measure and the 96px section gap — the body is
          otherwise still the undecided scaffold, and this does not change that. */}
      <div className="home-layout">
        <div className="home-eyebrow">
          <BrandBadge label="Bharat Stack by WECARE.DIGITAL" />
        </div>
      </div>
    </main>
    <style jsx>{`
      .home-shell{
        min-height:calc(100vh - 69px);
        padding-top:108px;
        box-sizing:border-box;
        background:#fff;
      }
      .home-layout{
        width:100%;
        max-width:1300px;
        margin:0 auto;
        padding:80px 24px 96px;
        box-sizing:border-box;
        display:flex;
        flex-direction:column;
        gap:96px;
      }
      /* .home-layout is a flex column, whose default align-items:stretch would
         pull the pill out to the full 1300px measure. This keeps it at its own
         width without changing the canvas for whatever sections land here next.
         It has to be a wrapper rather than a prop or className on the badge:
         styled-jsx does not scope composite components, so anything passed in
         from this page would arrive unstyled. */
      .home-eyebrow{
        align-self:flex-start;
      }
      @media(max-width:767px){
        .home-shell{min-height:calc(100vh - 85px);padding-top:96px}
        .home-layout{padding:48px 16px 64px;gap:64px}
      }
    `}</style>
  </>
);

export default HomePage;
