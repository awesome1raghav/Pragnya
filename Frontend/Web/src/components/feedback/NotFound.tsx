import Link from 'next/link';
import styles from './not-found.module.css';

/* Every address that is not built, or names something that does not exist, lands here with HTTP 404. */
export default function NotFound() {
  return <main className={styles.page}>
    <div className={styles.content}>
      <span className={styles.brand}>NEXTRON</span>
      <p className={styles.code}>404</p>
      <h1>Page not found</h1>
      <p className={styles.description}>This address is not part of the workspace, or it is not built yet.</p>
      <div className={styles.links}>
        <Link href='/'>Home</Link>
        <Link href='/dashboard'>Open the dashboard</Link>
      </div>
    </div>
  </main>;
}
