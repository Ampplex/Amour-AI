import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { Platform } from 'react-native';
import * as WebBrowser from 'expo-web-browser';
import * as AuthSession from 'expo-auth-session';
import * as Linking from 'expo-linking';
import { GoogleSignin, statusCodes } from '@react-native-google-signin/google-signin';
import { GOOGLE_CONFIG, API_CONFIG } from '../constants/authConfig';
import { clearFeedMemoryCache } from '../services/feedService';

WebBrowser.maybeCompleteAuthSession();

export interface GoogleUser {
  id: string;
  email: string;
  name: string;
  given_name?: string;
  family_name?: string;
  picture?: string;
  verified_email?: boolean;
  namespace?: string;
  token?: string;
}

interface AuthContextType {
  user: GoogleUser | null;
  loading: boolean;
  isAuthReady: boolean;
  error: string | null;
  pendingGoogleSession: boolean;
  signInWithGoogle: () => Promise<GoogleUser | null>;
  signUpWithGoogle: () => Promise<GoogleUser | null>;
  completeGoogleDevSession: (email?: string, name?: string) => void;
  submitTokenUrl: (url: string) => Promise<boolean>;
  dismissPendingSession: () => void;
  logout: () => Promise<void>;
  clearError: () => void;
  fetchGoogleUserInfo: (token: string) => Promise<GoogleUser | null>;
  setUser: (user: GoogleUser | null) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const discovery: AuthSession.DiscoveryDocument = {
  authorizationEndpoint: 'https://accounts.google.com/o/oauth2/v2/auth',
  tokenEndpoint: 'https://oauth2.googleapis.com/token',
  revocationEndpoint: 'https://oauth2.googleapis.com/revoke',
  userInfoEndpoint: 'https://openidconnect.googleapis.com/v1/userinfo',
};

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<GoogleUser | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [isAuthReady, setIsAuthReady] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingGoogleSession, setPendingGoogleSession] = useState<boolean>(false);

  useEffect(() => {
    // Safety fallback: Ensure isAuthReady never stays false for more than 2 seconds
    const safetyTimeout = setTimeout(() => {
      setIsAuthReady(true);
    }, 2000);

    try {
      GoogleSignin.configure({
        webClientId: GOOGLE_CONFIG.clientId,
        offlineAccess: false,
      });
      console.log('[GoogleSignin] Configured successfully with webClientId:', GOOGLE_CONFIG.clientId);

      GoogleSignin.signInSilently()
        .then((currentUser) => {
          if (currentUser?.data?.user) {
            const u = currentUser.data.user;
            setUser({
              id: u.id,
              name: u.name || `${u.givenName || ''} ${u.familyName || ''}`.trim() || 'Google User',
              email: u.email,
              picture: u.photo || undefined,
              given_name: u.givenName || undefined,
              family_name: u.familyName || undefined,
              verified_email: true,
              namespace: u.id,
            });
            console.log('[GoogleSignin] Restored active session for:', u.email);
          }
        })
        .catch(() => {
          // No stored session
        })
        .finally(() => {
          clearTimeout(safetyTimeout);
          setIsAuthReady(true);
        });
    } catch (e) {
      console.log('[GoogleSignin] configure warning:', e);
      clearTimeout(safetyTimeout);
      setIsAuthReady(true);
    }

    return () => clearTimeout(safetyTimeout);
  }, []);

  const [request, response, promptAsync] = AuthSession.useAuthRequest(
    {
      clientId: GOOGLE_CONFIG.clientId,
      scopes: ['openid', 'profile', 'email'],
      responseType: AuthSession.ResponseType.Token,
      redirectUri: GOOGLE_CONFIG.redirectUri,
      usePKCE: false,
    },
    discovery
  );

  const fetchGoogleUserInfo = async (token: string) => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetch('https://www.googleapis.com/userinfo/v2/me', {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!res.ok) {
        throw new Error('Failed to retrieve user profile from Google.');
      }

      const userData: GoogleUser = await res.json();
      setUser(userData);
      setLoading(false);
      return userData;
    } catch (err: any) {
      setError(err?.message || 'Error fetching Google user profile.');
      setLoading(false);
      return null;
    }
  };

  useEffect(() => {
    if (response?.type === 'success') {
      const { access_token } = response.params;
      if (access_token) {
        fetchGoogleUserInfo(access_token);
      }
    } else if (response?.type === 'error') {
      setError(response.error?.message || 'Google authentication encountered an error.');
      setLoading(false);
    } else if (response?.type === 'dismiss' || response?.type === 'cancel') {
      setLoading(false);
    }
  }, [response]);

  useEffect(() => {
    const handleIncomingUrl = (event: { url: string }) => {
      console.log('[Google Auth] Incoming deep link:', event.url);
      const tokenMatch = event.url.match(/[#?&]access_token=([^&]+)/);
      if (tokenMatch) {
        const token = decodeURIComponent(tokenMatch[1]);
        fetchGoogleUserInfo(token);
        try {
          WebBrowser.dismissAuthSession();
        } catch {}
      }
    };

    const sub = Linking.addEventListener('url', handleIncomingUrl);

    Linking.getInitialURL().then((initialUrl) => {
      if (initialUrl && initialUrl.includes('access_token=')) {
        handleIncomingUrl({ url: initialUrl });
      }
    });

    return () => {
      sub.remove();
    };
  }, []);

  const triggerGoogleAuth = async (): Promise<GoogleUser | null> => {
    setError(null);
    setLoading(true);

    // Try native Google Sign-In first (Google Play Services on Android)
    try {
      await GoogleSignin.hasPlayServices({ showPlayServicesUpdateDialog: true });
      const signinResult = await GoogleSignin.signIn();
      console.log('[Google Auth] Native result:', JSON.stringify(signinResult));

      if (signinResult.type === 'success' && signinResult.data?.user) {
        const u = signinResult.data.user;
        const idToken = signinResult.data.idToken;

        let googleUser: GoogleUser = {
          id: u.id,
          name: u.name || `${u.givenName || ''} ${u.familyName || ''}`.trim() || 'Google User',
          email: u.email,
          picture: u.photo || undefined,
          given_name: u.givenName || undefined,
          family_name: u.familyName || undefined,
          verified_email: true,
          namespace: u.id,
        };

        // Sync with Django PostgreSQL backend
        try {
          const res = await fetch(`${API_CONFIG.baseUrl}/auth/google/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              id_token: idToken || '',
              profile: {
                id: u.id,
                email: u.email,
                name: u.name,
                given_name: u.givenName,
                family_name: u.familyName,
                picture: u.photo,
              },
            }),
          });
          if (res.ok) {
            const data = await res.json();
            const bUser = data.user;
            googleUser = {
              id: bUser.id,
              name: bUser.name,
              email: bUser.email,
              picture: bUser.picture,
              given_name: bUser.given_name,
              family_name: bUser.family_name,
              verified_email: bUser.verified_email,
              namespace: bUser.namespace,
              token: data.access_token,
            };
            console.log('[Auth] Django PostgreSQL registration saved, namespace:', bUser.namespace);
          }
        } catch (syncErr) {
          console.warn('[Auth] Django backend sync notice:', syncErr);
        }

        setUser(googleUser);
        setLoading(false);
        return googleUser;
      } else if (signinResult.type === 'cancelled') {
        console.log('[Google Auth] User cancelled native sign-in dialog');
        setLoading(false);
        return null;
      }
    } catch (nativeErr: any) {
      console.log('[Google Auth] Native Sign In error/exception:', nativeErr);

      if (nativeErr.code === statusCodes.SIGN_IN_CANCELLED) {
        setLoading(false);
        return null;
      }

      if (nativeErr.code === statusCodes.IN_PROGRESS) {
        // Sign-in already running
        setLoading(false);
        return null;
      }

      if (nativeErr.code === statusCodes.PLAY_SERVICES_NOT_AVAILABLE) {
        setError('Google Play Services is not available or outdated.');
        setLoading(false);
        return null;
      }

      // On Android native app, do not fall back to browser so user never gets a confusing dual sign-in
      if (Platform.OS === 'android') {
        const errorMsg =
          nativeErr.code === '10'
            ? 'Google Play Services is updating client credentials (code 10). Please retry in 1 minute.'
            : nativeErr.message || 'Google Sign-In failed. Please try again.';
        setError(errorMsg);
        setLoading(false);
        return null;
      }

      // If native module is missing (e.g. running inside web or Expo Go), fallback to WebBrowser
      console.log('[Google Auth] Falling back to WebBrowser AuthSession...');
    }

    // Fallback: WebBrowser AuthSession (useful if opened in Expo Go or web)
    try {
      if (!request || !request.url) {
        setError('Authentication request is initializing. Please tap again in a moment.');
        setLoading(false);
        return null;
      }

      const returnUrl = AuthSession.getDefaultReturnUrl();
      const proxyStartUrl = `https://auth.expo.io/@ankesh-kumar/amour-ai/start?authUrl=${encodeURIComponent(
        request.url
      )}&returnUrl=${encodeURIComponent(returnUrl)}`;

      const result = await WebBrowser.openAuthSessionAsync(proxyStartUrl, returnUrl, {
        createTask: false,
      });

      if (result.type === 'success' && result.url) {
        const tokenMatch = result.url.match(/[#?&]access_token=([^&]+)/);
        const accessToken = tokenMatch ? decodeURIComponent(tokenMatch[1]) : null;

        if (accessToken) {
          const u = await fetchGoogleUserInfo(accessToken);
          return u;
        } else {
          const parsed = request.parseReturnUrl(result.url);
          if (parsed.type === 'success' && parsed.params.access_token) {
            const u = await fetchGoogleUserInfo(parsed.params.access_token);
            return u;
          } else {
            setError('Could not extract access token from Google.');
            setLoading(false);
            return null;
          }
        }
      } else if (result.type === 'dismiss' || result.type === 'cancel') {
        setLoading(false);
        setPendingGoogleSession(true);
        return null;
      } else {
        setLoading(false);
        return null;
      }
    } catch (err: any) {
      console.error('[Google Auth] Browser fallback error:', err);
      setError(err?.message || 'Unable to open Google sign-in window.');
      setLoading(false);
      return null;
    }
  };

  const completeGoogleDevSession = (customEmail?: string, customName?: string) => {
    setUser({
      id: '108392039281928391203',
      email: customEmail || 'ankesh3905222@gmail.com',
      name: customName || 'Ankesh Kumar',
      given_name: 'Ankesh',
      family_name: 'Kumar',
      picture: 'https://lh3.googleusercontent.com/a/ACg8ocL81b9_3gq9Zc_w2Gg4K3g8=s200-c',
      verified_email: true,
    });
    setPendingGoogleSession(false);
  };

  const submitTokenUrl = async (rawUrl: string): Promise<boolean> => {
    const tokenMatch = rawUrl.match(/[#?&]access_token=([^&]+)/);
    if (tokenMatch) {
      const token = decodeURIComponent(tokenMatch[1]);
      const res = await fetchGoogleUserInfo(token);
      if (res) {
        setPendingGoogleSession(false);
        return true;
      }
    }
    return false;
  };

  const dismissPendingSession = () => {
    setPendingGoogleSession(false);
  };

  const logout = async () => {
    try {
      await GoogleSignin.signOut();
    } catch {}
    clearFeedMemoryCache();
    setUser(null);
    setError(null);
    setPendingGoogleSession(false);
  };

  const clearError = () => {
    setError(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        isAuthReady,
        error,
        pendingGoogleSession,
        signInWithGoogle: triggerGoogleAuth,
        signUpWithGoogle: triggerGoogleAuth,
        completeGoogleDevSession,
        submitTokenUrl,
        dismissPendingSession,
        logout,
        clearError,
        fetchGoogleUserInfo,
        setUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
