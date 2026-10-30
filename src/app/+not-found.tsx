import React, { useEffect } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';
import * as Linking from 'expo-linking';
import { useAuth } from '../context/AuthContext';
import { theme } from '../constants/theme';
import AmourLogoVector from '../components/AmourLogoVector';

export default function NotFoundScreen() {
  const router = useRouter();
  const { user, fetchGoogleUserInfo } = useAuth();

  useEffect(() => {
    const handlePotentialDeepLink = async () => {
      try {
        const url = await Linking.getInitialURL();
        if (url && url.includes('access_token=')) {
          const match = url.match(/[#?&]access_token=([^&]+)/);
          if (match) {
            const token = decodeURIComponent(match[1]);
            const u = await fetchGoogleUserInfo(token);
            if (u) {
              router.replace('/(tabs)');
              return;
            }
          }
        }
      } catch {}

      router.replace(user ? '/(tabs)' : '/login');
    };

    handlePotentialDeepLink();
  }, [user]);

  return (
    <View style={styles.container}>
      <AmourLogoVector size={100} showText={false} animated={false} />
      <Text style={styles.text}>Redirecting to Amour AI...</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000000',
    alignItems: 'center',
    justifyContent: 'center',
  },
  text: {
    color: '#8E8E93',
    fontSize: 14,
    marginTop: 20,
  },
});
