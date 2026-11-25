import Link from 'next/link';

/* Every address that is not built, or names something that does not exist, lands here with HTTP 404.
   Styles: the nx404-* rules in src/styles/globals.css. */
export default function NotFound() {
  return <main className='nx404'>
    <div className='nx404-content'>
      <span className='nx404-brand'>NEXTRON</span>
      <p className='nx404-code'>404</p>
      <h1>Page not found</h1>
      <p className='nx404-description'>This address is not part of the workspace, or it is not built yet.</p>
      <div className='nx404-links'>
        <Link href='/'>Home</Link>
        <Link href='/dashboard'>Open the dashboard</Link>
      </div>
    </div>
  </main>;
}
