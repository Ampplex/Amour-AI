import React, { useEffect } from 'react';
import { View, Text, ActivityIndicator, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';
import * as Linking from 'expo-linking';
import { useAuth } from '../context/AuthContext';
import { theme } from '../constants/theme';
import AmourLogoVector from '../components/AmourLogoVector';

export default function ExpoAuthSessionScreen() {
  const router = useRouter();
  const { user, fetchGoogleUserInfo } = useAuth();

  useEffect(() => {
    if (user) {
      router.replace('/(tabs)');
      return;
    }

    let isMounted = true;

    const parseAndLogin = async () => {
      try {
        const url = await Linking.getInitialURL();
        console.log('[expo-auth-session] Route mounted with URL:', url);
        if (url && url.includes('access_token=')) {
          const match = url.match(/[#?&]access_token=([^&]+)/);
          if (match && isMounted) {
            const token = decodeURIComponent(match[1]);
            const u = await fetchGoogleUserInfo(token);
            if (u && isMounted) {
              router.replace('/(tabs)');
              return;
            }
          }
        }
      } catch (err) {
        console.error('[expo-auth-session] Parse error:', err);
      }

      // If no token found or already processed, redirect after brief check
      const timer = setTimeout(() => {
        if (isMounted) {
          router.replace(user ? '/(tabs)' : '/login');
        }
      }, 1500);

      return () => clearTimeout(timer);
    };

    parseAndLogin();

    return () => {
      isMounted = false;
    };
  }, [user]);

  return (
    <View style={styles.container}>
      <AmourLogoVector size={110} showText={false} animated={false} />
      <ActivityIndicator size="large" color={theme.colors.accent} style={styles.spinner} />
      <Text style={styles.title}>Completing Sign-In</Text>
      <Text style={styles.subtitle}>Verifying Google credentials...</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000000',
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 24,
  },
  spinner: {
    marginTop: 28,
    marginBottom: 16,
  },
  title: {
    color: '#FFFFFF',
    fontSize: 18,
    fontWeight: '700',
    letterSpacing: 0.3,
    marginBottom: 6,
  },
  subtitle: {
    color: '#8E8E93',
    fontSize: 13,
  },
});
