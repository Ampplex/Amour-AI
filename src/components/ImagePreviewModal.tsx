import React, { useEffect } from 'react';
import {
  StyleSheet,
  View,
  Text,
  Image,
  TouchableOpacity,
  Dimensions,
  Platform,
  TouchableWithoutFeedback,
  BackHandler,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Svg, { Path, Defs, LinearGradient, Stop, Rect } from 'react-native-svg';

const { width, height } = Dimensions.get('window');

function CloseIcon({ size = 20, color = '#FFFFFF' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M18 6L6 18M6 6l12 12"
        stroke={color}
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

interface ImagePreviewModalProps {
  visible: boolean;
  imageUrl?: string | null;
  name: string;
  tagline?: string;
  borderColor?: string;
  onClose: () => void;
  onResume?: () => void;
}

export default function ImagePreviewModal({
  visible,
  imageUrl,
  name,
  tagline,
  borderColor = '#F43F5E',
  onClose,
}: ImagePreviewModalProps) {
  useEffect(() => {
    if (!visible) return;
    const backHandler = BackHandler.addEventListener('hardwareBackPress', () => {
      onClose();
      return true;
    });
    return () => backHandler.remove();
  }, [visible, onClose]);

  if (!visible) return null;

  return (
    <View style={[StyleSheet.absoluteFill, styles.overlayWrapper]}>
      <TouchableWithoutFeedback onPress={onClose}>
        <View style={styles.netflixBackdrop}>
          {/* Full-width Wide Photo Covering Screen Width */}
          {imageUrl ? (
            <Image
              source={{ uri: imageUrl }}
              style={styles.widescreenImage}
              resizeMode="cover"
            />
          ) : (
            <View style={[styles.fallbackHero, { backgroundColor: '#121218' }]}>
              <Text style={[styles.fallbackInitial, { color: borderColor }]}>
                {name ? name.charAt(0).toUpperCase() : 'A'}
              </Text>
            </View>
          )}

          {/* Dark Moody Low-Opacity Overlay - Inspired by Netflix Paused Screen */}
          <View style={styles.darkTintOverlay} />

          {/* Smooth Top & Bottom Cinematic Gradient Vignettes */}
          <Svg height="100%" width="100%" style={StyleSheet.absoluteFill}>
            <Defs>
              <LinearGradient id="previewTopFade" x1="0" y1="0" x2="0" y2="0.32">
                <Stop offset="0" stopColor="#000000" stopOpacity="0.82" />
                <Stop offset="1" stopColor="#000000" stopOpacity="0" />
              </LinearGradient>
              <LinearGradient id="previewBottomFade" x1="0" y1="0.55" x2="0" y2="1">
                <Stop offset="0" stopColor="#000000" stopOpacity="0" />
                <Stop offset="0.6" stopColor="#000000" stopOpacity="0.7" />
                <Stop offset="1" stopColor="#060609" stopOpacity="0.95" />
              </LinearGradient>
            </Defs>
            <Rect x="0" y="0" width="100%" height="100%" fill="url(#previewTopFade)" />
            <Rect x="0" y="0" width="100%" height="100%" fill="url(#previewBottomFade)" />
          </Svg>

          <SafeAreaView style={styles.safeArea} edges={['top', 'bottom']}>
            {/* Top Bar: Close Button */}
            <View style={styles.topBar}>
              <TouchableOpacity
                style={styles.glassCircleBtn}
                onPress={onClose}
                activeOpacity={0.7}
                hitSlop={{ top: 14, bottom: 14, left: 14, right: 14 }}
                accessibilityLabel="Close"
              >
                <CloseIcon size={20} color="#FFFFFF" />
              </TouchableOpacity>
            </View>

            {/* Bottom Metadata */}
            <View style={styles.bottomMetaContainer}>
              <Text style={styles.personaTitle} numberOfLines={1}>
                {name}
              </Text>

              {tagline ? (
                <Text style={styles.personaTagline} numberOfLines={2}>
                  {tagline}
                </Text>
              ) : null}
            </View>
          </SafeAreaView>
        </View>
      </TouchableWithoutFeedback>
    </View>
  );
}

const styles = StyleSheet.create({
  overlayWrapper: {
    zIndex: 99999,
    elevation: 99,
  },
  netflixBackdrop: {
    flex: 1,
    backgroundColor: '#060609',
    position: 'relative',
    justifyContent: 'space-between',
  },
  widescreenImage: {
    position: 'absolute',
    top: 0,
    left: 0,
    width: '100%',
    height: '100%',
  },
  fallbackHero: {
    position: 'absolute',
    top: 0,
    left: 0,
    width: '100%',
    height: '100%',
    alignItems: 'center',
    justifyContent: 'center',
  },
  fallbackInitial: {
    fontFamily: 'ChangaOne-Regular',
    fontSize: 90,
  },
  darkTintOverlay: {
    ...StyleSheet.absoluteFill,
    backgroundColor: 'rgba(0, 0, 0, 0.44)',
  },
  safeArea: {
    flex: 1,
    justifyContent: 'space-between',
  },
  topBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'flex-start',
    paddingHorizontal: 20,
    paddingTop: Platform.OS === 'android' ? 12 : 6,
    zIndex: 10,
  },
  glassCircleBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: 'rgba(0, 0, 0, 0.55)',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.18)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  bottomMetaContainer: {
    paddingHorizontal: 22,
    paddingBottom: Platform.OS === 'android' ? 28 : 20,
    zIndex: 10,
    gap: 6,
  },
  personaTitle: {
    fontFamily: 'ChangaOne-Regular',
    fontSize: 32,
    color: '#FFFFFF',
    letterSpacing: 0.4,
    textShadowColor: 'rgba(0, 0, 0, 0.85)',
    textShadowOffset: { width: 0, height: 2 },
    textShadowRadius: 8,
  },
  personaTagline: {
    color: '#D4D4D8',
    fontSize: 14,
    lineHeight: 20,
    opacity: 0.9,
  },
});
