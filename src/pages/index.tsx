import React from 'react';
import Head from 'next/head';

const HomePage: React.FC = () => (
  <>
    <Head>
      <title>Bharat Stack by WECARE.DIGITAL</title>
      <meta name="description" content="Bharat Stack by WECARE.DIGITAL." />
      <link rel="canonical" href="https://stack.wecare.digital/" />
    </Head>
    <main className="home-shell" aria-label="Bharat Stack home">
      <div className="home-layout" />
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
      @media(max-width:767px){
        .home-shell{min-height:calc(100vh - 85px);padding-top:96px}
        .home-layout{padding:48px 16px 64px;gap:64px}
      }
    `}</style>
  </>
);

export default HomePage;
