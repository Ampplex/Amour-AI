import React, { useEffect, useRef, useCallback } from 'react';
import {
  StyleSheet,
  View,
  Pressable,
  Animated,
  Dimensions,
} from 'react-native';
import { router } from 'expo-router';
import { theme } from '../constants/theme';
import AmourLogoVector from '../components/AmourLogoVector';
import { useAuth } from '../context/AuthContext';

const { width } = Dimensions.get('window');

export default function StartScreen() {
  const { user, isAuthReady } = useAuth();
  const navigatedRef = useRef(false);
  const pulseAnim = useRef(new Animated.Value(0.4)).current;

  const navigateNext = useCallback(() => {
    if (navigatedRef.current) return;
    navigatedRef.current = true;
    if (user) {
      router.replace('/(tabs)');
    } else {
      router.replace('/login');
    }
  }, [user]);

  useEffect(() => {
    // Subtle pulsing for the tagline while loading
    Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, {
          toValue: 0.9,
          duration: 900,
          useNativeDriver: true,
        }),
        Animated.timing(pulseAnim, {
          toValue: 0.4,
          duration: 900,
          useNativeDriver: true,
        }),
      ])
    ).start();
  }, [pulseAnim]);

  // Navigate when auth check completes, or guaranteed fallback after 2 seconds
  useEffect(() => {
    const timer = setTimeout(() => {
      navigateNext();
    }, isAuthReady ? 1200 : 2200);
    return () => clearTimeout(timer);
  }, [isAuthReady, navigateNext]);

  return (
    <Pressable
      style={styles.container}
      onPress={navigateNext}
      accessibilityRole="button"
      accessibilityLabel="Tap to skip to home"
    >
      <View style={styles.centerContent}>
        {/* Full vector logo with animated brackets and Amour AI typography */}
        <AmourLogoVector
          maxWidth={Math.min(width * 0.85, 340)}
          showText={true}
          animated={true}
          onAnimationComplete={navigateNext}
        />
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.background,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 24,
  },
  centerContent: {
    alignItems: 'center',
    justifyContent: 'center',
  },
});
