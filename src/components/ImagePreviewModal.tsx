import React from 'react';
import {
  StyleSheet,
  View,
  Text,
  Modal,
  Image,
  TouchableOpacity,
  Dimensions,
  Platform,
  TouchableWithoutFeedback,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Svg, { Path } from 'react-native-svg';

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
}

export default function ImagePreviewModal({
  visible,
  imageUrl,
  name,
  tagline,
  borderColor = '#F43F5E',
  onClose,
}: ImagePreviewModalProps) {
  if (!visible) return null;

  return (
    <Modal
      visible={visible}
      transparent={true}
      animationType="fade"
      statusBarTranslucent={true}
      onRequestClose={onClose}
    >
      <TouchableWithoutFeedback onPress={onClose}>
        <View style={styles.backdrop}>
          <SafeAreaView style={styles.safeArea} edges={['top', 'bottom']}>
            {/* Top Bar */}
            <View style={styles.topBar}>
              <View style={styles.titleContainer}>
                <Text style={styles.personaName} numberOfLines={1}>
                  {name}
                </Text>
                {tagline ? (
                  <Text style={styles.personaTagline} numberOfLines={1}>
                    {tagline}
                  </Text>
                ) : null}
              </View>

              <TouchableOpacity
                style={styles.closeBtn}
                onPress={onClose}
                activeOpacity={0.7}
                hitSlop={{ top: 14, bottom: 14, left: 14, right: 14 }}
                accessibilityLabel="Close image preview"
              >
                <CloseIcon size={20} color="#FFFFFF" />
              </TouchableOpacity>
            </View>

            {/* Image Center View */}
            <TouchableWithoutFeedback>
              <View style={styles.imageContainer}>
                {imageUrl ? (
                  <Image
                    source={{ uri: imageUrl }}
                    style={styles.fullImage}
                    resizeMode="contain"
                  />
                ) : (
                  <View style={[styles.fallbackContainer, { borderColor }]}>
                    <Text style={[styles.fallbackInitial, { color: borderColor }]}>
                      {name ? name.charAt(0).toUpperCase() : 'A'}
                    </Text>
                    <Text style={styles.fallbackName}>{name}</Text>
                  </View>
                )}
              </View>
            </TouchableWithoutFeedback>

            {/* Bottom Info Footer */}
            <View style={styles.bottomBar}>
              <Text style={styles.tapToCloseHint}>Tap outside or close to return</Text>
            </View>
          </SafeAreaView>
        </View>
      </TouchableWithoutFeedback>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.95)',
    justifyContent: 'space-between',
  },
  safeArea: {
    flex: 1,
    justifyContent: 'space-between',
  },
  topBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingVertical: 14,
    zIndex: 10,
  },
  titleContainer: {
    flex: 1,
    marginRight: 16,
    gap: 2,
  },
  personaName: {
    color: '#FFFFFF',
    fontFamily: 'ChangaOne-Regular',
    fontSize: 20,
    letterSpacing: 0.3,
  },
  personaTagline: {
    color: '#A1A1AA',
    fontSize: 13,
  },
  closeBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: 'rgba(255, 255, 255, 0.12)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  imageContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 16,
    paddingVertical: 20,
  },
  fullImage: {
    width: width - 32,
    height: height * 0.68,
    borderRadius: 16,
    maxHeight: 600,
  },
  fallbackContainer: {
    width: width * 0.75,
    height: width * 0.75,
    borderRadius: (width * 0.75) / 2,
    backgroundColor: '#16161A',
    borderWidth: 2,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
  },
  fallbackInitial: {
    fontFamily: 'ChangaOne-Regular',
    fontSize: 72,
  },
  fallbackName: {
    color: '#FFFFFF',
    fontFamily: 'ChangaOne-Regular',
    fontSize: 22,
  },
  bottomBar: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 16,
  },
  tapToCloseHint: {
    color: '#71717A',
    fontSize: 12,
    letterSpacing: 0.2,
  },
});
