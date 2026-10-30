import React, { useEffect, useRef } from 'react';
import {
  StyleSheet,
  View,
  Text,
  Modal,
  TouchableOpacity,
  Animated,
  Dimensions,
  TouchableWithoutFeedback,
  Platform,
} from 'react-native';
import Svg, { Path, Circle } from 'react-native-svg';

const { width } = Dimensions.get('window');

export type AlertType = 'info' | 'success' | 'warning' | 'danger';

export interface AlertButton {
  text: string;
  style?: 'default' | 'cancel' | 'destructive' | 'primary';
  onPress?: () => void;
}

export interface AlertConfig {
  title: string;
  message?: string;
  type?: AlertType;
  buttons?: AlertButton[];
  onDismiss?: () => void;
}

interface ProfessionalAlertModalProps {
  visible: boolean;
  config: AlertConfig | null;
  onClose: () => void;
}

// Sleek SVG Icons - Zero Emojis
function DangerIcon({ color }: { color: string }) {
  return (
    <Svg width={26} height={26} viewBox="0 0 24 24" fill="none">
      <Path
        d="M12 9v4M12 17h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

function SuccessIcon({ color }: { color: string }) {
  return (
    <Svg width={26} height={26} viewBox="0 0 24 24" fill="none">
      <Circle cx="12" cy="12" r="10" stroke={color} strokeWidth="2" />
      <Path
        d="M8 12l2.8 2.8L16 9.5"
        stroke={color}
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

function WarningIcon({ color }: { color: string }) {
  return (
    <Svg width={26} height={26} viewBox="0 0 24 24" fill="none">
      <Circle cx="12" cy="12" r="10" stroke={color} strokeWidth="2" />
      <Path d="M12 8v5M12 16h.01" stroke={color} strokeWidth="2.2" strokeLinecap="round" />
    </Svg>
  );
}

function InfoIcon({ color }: { color: string }) {
  return (
    <Svg width={26} height={26} viewBox="0 0 24 24" fill="none">
      <Path
        d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <Circle cx="12" cy="11" r="1.5" fill={color} />
      <Path d="M12 12.5V15" stroke={color} strokeWidth="1.8" strokeLinecap="round" />
    </Svg>
  );
}

export default function ProfessionalAlertModal({
  visible,
  config,
  onClose,
}: ProfessionalAlertModalProps) {
  const scaleAnim = useRef(new Animated.Value(0.9)).current;
  const opacityAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (visible) {
      Animated.parallel([
        Animated.spring(scaleAnim, {
          toValue: 1,
          tension: 80,
          friction: 9,
          useNativeDriver: true,
        }),
        Animated.timing(opacityAnim, {
          toValue: 1,
          duration: 180,
          useNativeDriver: true,
        }),
      ]).start();
    } else {
      scaleAnim.setValue(0.9);
      opacityAnim.setValue(0);
    }
  }, [visible, scaleAnim, opacityAnim]);

  if (!visible || !config) return null;

  // Derive theme colors from type
  let accentColor = '#F43F5E'; // default rose
  let iconComponent = <InfoIcon color={accentColor} />;

  const inferredType = config.type || 'info';

  if (inferredType === 'danger') {
    accentColor = '#F43F5E';
    iconComponent = <DangerIcon color={accentColor} />;
  } else if (inferredType === 'success') {
    accentColor = '#10B981';
    iconComponent = <SuccessIcon color={accentColor} />;
  } else if (inferredType === 'warning') {
    accentColor = '#F59E0B';
    iconComponent = <WarningIcon color={accentColor} />;
  } else {
    accentColor = '#F43F5E';
    iconComponent = <InfoIcon color={accentColor} />;
  }

  const buttons = config.buttons && config.buttons.length > 0
    ? config.buttons
    : [{ text: 'OK', style: 'primary' as const, onPress: () => {} }];

  const handleButtonPress = (btn: AlertButton) => {
    onClose();
    if (btn.onPress) {
      // Execute after modal dismisses
      setTimeout(() => {
        btn.onPress?.();
      }, 100);
    }
  };

  const isDoubleButton = buttons.length === 2;

  return (
    <Modal
      transparent
      visible={visible}
      animationType="none"
      statusBarTranslucent
      onRequestClose={onClose}
    >
      <TouchableWithoutFeedback onPress={onClose}>
        <Animated.View style={[styles.backdrop, { opacity: opacityAnim }]}>
          <TouchableWithoutFeedback>
            <Animated.View
              style={[
                styles.dialogCard,
                {
                  transform: [{ scale: scaleAnim }],
                  opacity: opacityAnim,
                },
              ]}
            >
              {/* Top Accent Light Beam */}
              <View style={[styles.topBeam, { backgroundColor: accentColor }]} />

              {/* Icon Badge */}
              <View
                style={[
                  styles.iconBadge,
                  {
                    backgroundColor: accentColor + '18',
                    borderColor: accentColor + '40',
                  },
                ]}
              >
                {iconComponent}
              </View>

              {/* Title */}
              <Text style={styles.titleText}>{config.title}</Text>

              {/* Message */}
              {config.message ? (
                <Text style={styles.messageText}>{config.message}</Text>
              ) : null}

              {/* Action Buttons */}
              <View
                style={[
                  styles.buttonContainer,
                  isDoubleButton ? styles.buttonRow : styles.buttonColumn,
                ]}
              >
                {buttons.map((btn, index) => {
                  const isCancel = btn.style === 'cancel';
                  const isDestructive = btn.style === 'destructive';
                  const isPrimary = btn.style === 'primary' || (!btn.style && !isCancel);

                  let btnBg = '#1A1A22';
                  let btnBorder = '#2D2D3B';
                  let textColor = '#9CA3AF';

                  if (isDestructive) {
                    btnBg = '#F43F5E';
                    btnBorder = '#F43F5E';
                    textColor = '#FFFFFF';
                  } else if (isPrimary) {
                    btnBg = accentColor;
                    btnBorder = accentColor;
                    textColor = '#FFFFFF';
                  } else if (isCancel) {
                    btnBg = '#14141C';
                    btnBorder = '#242432';
                    textColor = '#9CA3AF';
                  }

                  return (
                    <TouchableOpacity
                      key={index}
                      style={[
                        styles.button,
                        {
                          backgroundColor: btnBg,
                          borderColor: btnBorder,
                        },
                        isDoubleButton ? styles.buttonFlex : styles.buttonFull,
                      ]}
                      onPress={() => handleButtonPress(btn)}
                      activeOpacity={0.8}
                    >
                      <Text
                        style={[
                          styles.buttonText,
                          {
                            color: textColor,
                          },
                        ]}
                      >
                        {btn.text}
                      </Text>
                    </TouchableOpacity>
                  );
                })}
              </View>
            </Animated.View>
          </TouchableWithoutFeedback>
        </Animated.View>
      </TouchableWithoutFeedback>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.82)',
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 24,
  },
  dialogCard: {
    width: Math.min(width - 48, 380),
    backgroundColor: '#0D0D14',
    borderRadius: 22,
    borderWidth: 1.2,
    borderColor: '#22222E',
    paddingHorizontal: 22,
    paddingTop: 24,
    paddingBottom: 20,
    alignItems: 'center',
    overflow: 'hidden',
    ...Platform.select({
      android: {
        elevation: 20,
      },
      ios: {
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 10 },
        shadowOpacity: 0.5,
        shadowRadius: 20,
      },
    }),
  },
  topBeam: {
    position: 'absolute',
    top: 0,
    left: 40,
    right: 40,
    height: 2.5,
    borderRadius: 2,
    opacity: 0.85,
  },
  iconBadge: {
    width: 58,
    height: 58,
    borderRadius: 29,
    borderWidth: 1.5,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
  },
  titleText: {
    fontFamily: 'ChangaOne-Regular',
    fontSize: 20,
    color: '#FFFFFF',
    letterSpacing: 0.4,
    textAlign: 'center',
    marginBottom: 8,
  },
  messageText: {
    fontSize: 13.5,
    color: '#9CA3AF',
    textAlign: 'center',
    lineHeight: 20,
    marginBottom: 20,
    paddingHorizontal: 6,
  },
  buttonContainer: {
    width: '100%',
    marginTop: 4,
  },
  buttonRow: {
    flexDirection: 'row',
    gap: 10,
  },
  buttonColumn: {
    flexDirection: 'column',
    gap: 10,
  },
  button: {
    height: 48,
    borderRadius: 14,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 16,
  },
  buttonFlex: {
    flex: 1,
  },
  buttonFull: {
    width: '100%',
  },
  buttonText: {
    fontFamily: 'ChangaOne-Regular',
    fontSize: 14.5,
    letterSpacing: 0.4,
  },
});
