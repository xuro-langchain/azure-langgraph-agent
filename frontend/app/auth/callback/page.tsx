'use client';

import { useEffect, useState } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';

const handleCallback = async (code: string, scopes: string | null) => {
  let url = `/api/auth/callback?code=${encodeURIComponent(code)}`;
  if (scopes) {
    url += `&scopes=${encodeURIComponent(scopes)}`;
  }
  const response = await fetch(url, {
    method: 'GET',
    credentials: 'include',
  });
  return response;
};

export default function AuthCallback() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [status, setStatus] = useState('Processing authentication...');

  const code = searchParams.get('code');
  const error = searchParams.get('error');
  const scopes = searchParams.get('scope'); // Extract the scope param from the URL

  useEffect(() => {
    if (error) {
      setStatus(`Authentication failed: ${error}`);
      return;
    }
    if (code && !error) {
      handleCallback(code, scopes).then((response) => {
        if (response.ok) {
          setStatus('Authentication successful! Redirecting...');
          router.replace('/');
        } else {
          setStatus(`Authentication failed: ${response.status} - ${response.statusText}`);
        }
      }).catch((error) => {
        setStatus(`Authentication error: ${error.message}`);
      });
    } else {
      setStatus('Missing authentication parameters');
    }
  }, []);

  return (
    <div className="auth-container flex flex-col items-center justify-center min-h-screen">
      <h1>Authentication</h1>
      <div style={{ margin: '32px 0' }}>
        {status === 'Processing authentication...' && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <div className="spinner" style={{
              width: 48, height: 48, border: '5px solid #e9ecef', borderTop: '5px solid #0078d4', borderRadius: '50%', animation: 'spin 1s linear infinite', marginBottom: 24
            }} />
            <p style={{ color: '#0078d4', fontWeight: 500, fontSize: 18 }}>{status}</p>
          </div>
        )}
        {status !== 'Processing authentication...' && (
          <p style={{ color: status.startsWith('Authentication successful') ? '#28a745' : '#d32f2f', fontWeight: 500, fontSize: 18 }}>{status}</p>
        )}
      </div>
      <style>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
} 