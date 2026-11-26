/* Where the NEXTRON API lives. Set NEXT_PUBLIC_NEXTRON_API in Frontend/Web/.env.local to change it;
   this one default matches the backend's documented development address. */
export const API_BASE = (process.env.NEXT_PUBLIC_NEXTRON_API || 'http://localhost:8000/api/v1').replace(/\/$/, '');
