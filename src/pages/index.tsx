import React from 'react';
import Head from 'next/head';

const HomePage: React.FC = () => (
  <>
    <Head>
      <title>Bharat Stack by WECARE.DIGITAL</title>
      <meta name="description" content="Bharat Stack by WECARE.DIGITAL." />
      <link rel="canonical" href="https://stack.wecare.digital/" />
    </Head>
    <main className="home-shell" aria-label="Bharat Stack home" />
    <style jsx>{`
      .home-shell{
        min-height:calc(100vh - 69px);
        padding-top:96px;
        box-sizing:border-box;
        background:#fff;
      }
      @media(max-width:767px){
        .home-shell{min-height:calc(100vh - 85px);padding-top:88px}
      }
    `}</style>
  </>
);

export default HomePage;
