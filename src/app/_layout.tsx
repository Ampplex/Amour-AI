import React, { useEffect, useState } from 'react';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import * as WebBrowser from 'expo-web-browser';
import * as SplashScreen from 'expo-splash-screen';
import { useFonts } from 'expo-font';
import { theme } from '../constants/theme';
import { AuthProvider } from '../context/AuthContext';
import { AlertProvider } from '../context/AlertContext';

SplashScreen.preventAutoHideAsync().catch(() => {});

WebBrowser.maybeCompleteAuthSession();

export default function RootLayout() {
  const [loaded, error] = useFonts({
    'ChangaOne-Regular': require('../../assets/fonts/ChangaOne-Regular.ttf'),
    'ChangaOne-Italic': require('../../assets/fonts/ChangaOne-Italic.ttf'),
  });

  const [fallbackReady, setFallbackReady] = useState(false);

  useEffect(() => {
    // Safety timer: guarantees the native splash hides even if fonts fail or delay
    const timer = setTimeout(() => {
      setFallbackReady(true);
      SplashScreen.hideAsync().catch(() => {});
    }, 2500);
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (loaded || error) {
      SplashScreen.hideAsync().catch(() => {});
    }
  }, [loaded, error]);

  if (!loaded && !error && !fallbackReady) {
    return null;
  }

  return (
    <AuthProvider>
      <AlertProvider>
        <StatusBar style="light" />
        <Stack
          screenOptions={{
            headerShown: false,
            contentStyle: {
              backgroundColor: theme.colors.background,
            },
            animation: 'fade',
          }}
        >
          <Stack.Screen
            name="index"
            options={{
              animation: 'fade',
            }}
          />
          <Stack.Screen
            name="login"
            options={{
              animation: 'fade',
            }}
          />
          <Stack.Screen
            name="signup"
            options={{
              animation: 'slide_from_right',
            }}
          />
          <Stack.Screen
            name="forgot-password"
            options={{
              animation: 'slide_from_right',
            }}
          />
          <Stack.Screen
            name="(tabs)"
            options={{
              headerShown: false,
              animation: 'fade',
            }}
          />
          <Stack.Screen
            name="expo-auth-session"
            options={{
              animation: 'fade',
            }}
          />
          <Stack.Screen
            name="+not-found"
            options={{
              animation: 'fade',
            }}
          />
        </Stack>
      </AlertProvider>
    </AuthProvider>
  );
}
