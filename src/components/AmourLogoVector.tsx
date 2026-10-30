import React, { useEffect, useRef, useState } from 'react';
import { StyleSheet, Animated, Easing, Dimensions, StyleProp, ViewStyle } from 'react-native';
import Svg, { Path, G } from 'react-native-svg';
import { LOGO_DATA } from './logoData';

const { width } = Dimensions.get('window');

export interface AmourLogoVectorProps {
  size?: number;
  maxWidth?: number;
  showText?: boolean;
  animated?: boolean;
  style?: StyleProp<ViewStyle>;
  onAnimationComplete?: () => void;
}

/**
 * AmourLogoVector
 *
 * 100% Vector code rendering of the Amour AI branding.
 * 
 * - When showText=false: Displays only the iconic emblem (no text), perfectly centered.
 * - When showText=true: Displays the full lockup with typography.
 * - Brackets expand outward along their diagonal axes and smoothly return to (0, 0).
 * - Zero raster images, pure OLED black compatible.
 */
export default function AmourLogoVector({
  size = 150,
  maxWidth = 360,
  showText = true,
  animated = true,
  style,
  onAnimationComplete,
}: AmourLogoVectorProps) {
  const [offset, setOffset] = useState<number>(0);
  const expand = useRef(new Animated.Value(0)).current;
  const fade = useRef(new Animated.Value(animated ? 0 : 1)).current;

  useEffect(() => {
    if (!animated) {
      if (onAnimationComplete) {
        onAnimationComplete();
      }
      return;
    }

    // Fade-in
    Animated.timing(fade, {
      toValue: 1,
      duration: 350,
      easing: Easing.out(Easing.ease),
      useNativeDriver: true,
    }).start();

    // Drive SVG transform directly
    const listenerId = expand.addListener(({ value }) => {
      setOffset(value);
    });

    Animated.sequence([
      Animated.delay(150),
      // 1. Brackets expand outward
      Animated.timing(expand, {
        toValue: 1,
        duration: 550,
        easing: Easing.out(Easing.cubic),
        useNativeDriver: false,
      }),
      // Peak hold
      Animated.delay(80),
      // 2. Brackets glide back and reconstruct to original position
      Animated.timing(expand, {
        toValue: 0,
        duration: 650,
        easing: Easing.bezier(0.25, 0.1, 0.25, 1.0),
        useNativeDriver: false,
      }),
      // Hold completed logo briefly before invoking onAnimationComplete
      Animated.delay(350),
    ]).start(({ finished }) => {
      if (finished && onAnimationComplete) {
        onAnimationComplete();
      }
    });

    return () => {
      expand.removeListener(listenerId);
    };
  }, [animated, onAnimationComplete]);

  // Dimensions
  let W: number;
  let H: number;
  let viewBox: string;

  if (showText) {
    // Full lockup with text
    W = Math.round(Math.min(width * 0.90, maxWidth));
    H = Math.round(W * (LOGO_DATA.canvasHeight / LOGO_DATA.canvasWidth));
    viewBox = LOGO_DATA.viewBox;
  } else {
    // Emblem ONLY (no text)
    const emblemTarget = size || maxWidth || 110;
    W = Math.round(Math.min(width * 0.45, emblemTarget));
    H = Math.round(W * (LOGO_DATA.emblemOnly.height / LOGO_DATA.emblemOnly.width));
    viewBox = LOGO_DATA.emblemOnly.viewBox;
  }

  // Expansion distance in SVG units
  const svgShift = Math.round(offset * 28);

  return (
    <Animated.View style={[styles.container, { width: W, height: H, opacity: fade }, style]}>
      <Svg
        viewBox={viewBox}
        width={W}
        height={H}
        style={styles.svg}
      >
        {/* Optional Typography: Rendered only when showText=true */}
        {showText && (
          <Path
            d={LOGO_DATA.typography}
            fill="#FFFFFF"
            fillRule="evenodd"
          />
        )}

        {/* Static Center Node */}
        <Path
          d={LOGO_DATA.centerNode}
          fill="#FFFFFF"
        />

        {/* Top-Left Bracket: Expands up-left (-X, -Y), returns to (0, 0) */}
        <G transform={`translate(${-svgShift}, ${-svgShift})`}>
          <Path
            d={LOGO_DATA.bracketTopLeft}
            fill="#FFFFFF"
          />
        </G>

        {/* Bottom-Right Bracket: Expands down-right (+X, +Y), returns to (0, 0) */}
        <G transform={`translate(${svgShift}, ${svgShift})`}>
          <Path
            d={LOGO_DATA.bracketBottomRight}
            fill="#FFFFFF"
          />
        </G>
      </Svg>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'visible',
  },
  svg: {
    backgroundColor: 'transparent',
    overflow: 'visible',
  },
});
