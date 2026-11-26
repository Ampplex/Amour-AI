import React, { useState, useRef, useEffect } from 'react';
import {
  StyleSheet,
  View,
  Text,
  Modal,
  FlatList,
  TextInput,
  TouchableOpacity,
  Image,
  ActivityIndicator,
  Platform,
  ScrollView,
  Keyboard,
  Dimensions,
  Animated,
  Easing,
  Vibration,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Svg, { Path, Circle, Rect } from 'react-native-svg';
import * as Clipboard from 'expo-clipboard';
import MarkdownText from './MarkdownText';
import PersonaDetailModal from './PersonaDetailModal';
import ImagePreviewModal from './ImagePreviewModal';
import { PersonaItem, getPersonaCustomization } from '../services/personaService';
import { fetchChatHistory, sendChatMessage, deleteChatMessage, switchChatMessageVariant, editBotChatMessage } from '../services/chatService';
import { useAuth } from '../context/AuthContext';
import { showAlert } from '../context/AlertContext';
import AsyncStorage from '@react-native-async-storage/async-storage';

const { width } = Dimensions.get('window');

function cleanPersonaChipName(name?: string): string {
  if (!name) return '';
  const cleaned = name.split(/[\(\[\{]/)[0].trim();
  return cleaned || name;
}

function BackIcon({ size = 20, color = '#FFFFFF' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M15 18l-6-6 6-6"
        stroke={color}
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

function MenuIcon({ size = 18, color = '#FFFFFF' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M4 7h16M4 12h16M4 17h16"
        stroke={color}
        strokeWidth="2.2"
        strokeLinecap="round"
      />
    </Svg>
  );
}

function ChatSendIcon({ size = 16, color = '#FFFFFF' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M3.4 20.4l17.45-7.48c.81-.35.81-1.49 0-1.84L3.4 3.6c-.66-.29-1.39.2-1.39.91L2 9.12c0 .5.37.93.87.99L17 12 2.87 13.88c-.5.07-.87.49-.87 1l.01 4.61c0 .71.73 1.2 1.39.91z"
        fill={color}
      />
    </Svg>
  );
}

function InputUserIcon({ size = 26 }: { size?: number }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Circle cx="12" cy="12" r="11" fill="#1C1C1F" />
      <Circle cx="12" cy="9.2" r="3.4" fill="#D4D4D8" />
      <Path
        d="M6 18.8c0-2.8 2.7-5 6-5s6 2.2 6 5"
        fill="#D4D4D8"
      />
    </Svg>
  );
}

function SendArrowIcon({ size = 16, color = '#FFFFFF' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M5 12h14M12 5l7 7-7 7"
        stroke={color}
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

function BrainIcon({ size = 14, color = '#60A5FA' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M9.5 2A2.5 2.5 0 0 0 7 4.5V5A3 3 0 0 0 4 8v1a3 3 0 0 0-1 2.25c0 1.25.75 2.3 1.83 2.75A3 3 0 0 0 4 16v1a3 3 0 0 0 3 3h.5A2.5 2.5 0 0 0 10 22h.5a2.5 2.5 0 0 0 2.5-2.5V19a2.5 2.5 0 0 0-2.5-2.5H10v-3h1.5A2.5 2.5 0 0 0 14 11V8.5A2.5 2.5 0 0 0 11.5 6H10V4.5A2.5 2.5 0 0 0 7.5 2h2z"
        stroke={color}
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <Path
        d="M14.5 2A2.5 2.5 0 0 1 17 4.5V5a3 3 0 0 1 3 3v1a3 3 0 0 1 1 2.25c0 1.25-.75 2.3-1.83 2.75A3 3 0 0 1 20 16v1a3 3 0 0 1-3 3h-.5A2.5 2.5 0 0 1 14 22h-.5a2.5 2.5 0 0 1-2.5-2.5V19a2.5 2.5 0 0 1 2.5-2.5H14v-3h-1.5A2.5 2.5 0 0 1 10 11V8.5A2.5 2.5 0 0 1 12.5 6H14V4.5A2.5 2.5 0 0 1 16.5 2h-2z"
        stroke={color}
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

function CloseIcon({ size = 18, color = '#FFFFFF' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M18 6L6 18M6 6l12 12" stroke={color} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  );
}

function TypingDotsAnimation({ color = '#D4D4D8' }: { color?: string }) {
  const dot1 = useRef(new Animated.Value(0)).current;
  const dot2 = useRef(new Animated.Value(0)).current;
  const dot3 = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const createDotAnim = (dot: Animated.Value, delay: number) => {
      return Animated.loop(
        Animated.sequence([
          Animated.delay(delay),
          Animated.timing(dot, {
            toValue: -5,
            duration: 260,
            useNativeDriver: true,
          }),
          Animated.timing(dot, {
            toValue: 0,
            duration: 260,
            useNativeDriver: true,
          }),
          Animated.delay(360),
        ])
      );
    };

    const anim1 = createDotAnim(dot1, 0);
    const anim2 = createDotAnim(dot2, 140);
    const anim3 = createDotAnim(dot3, 280);

    anim1.start();
    anim2.start();
    anim3.start();

    return () => {
      anim1.stop();
      anim2.stop();
      anim3.stop();
    };
  }, [dot1, dot2, dot3]);

  return (
    <View style={styles.typingDotsContainer}>
      <Animated.View
        style={[
          styles.typingDot,
          {
            backgroundColor: color,
            transform: [{ translateY: dot1 }],
            opacity: dot1.interpolate({
              inputRange: [-5, 0],
              outputRange: [1, 0.45],
            }),
          },
        ]}
      />
      <Animated.View
        style={[
          styles.typingDot,
          {
            backgroundColor: color,
            transform: [{ translateY: dot2 }],
            opacity: dot2.interpolate({
              inputRange: [-5, 0],
              outputRange: [1, 0.45],
            }),
          },
        ]}
      />
      <Animated.View
        style={[
          styles.typingDot,
          {
            backgroundColor: color,
            transform: [{ translateY: dot3 }],
            opacity: dot3.interpolate({
              inputRange: [-5, 0],
              outputRange: [1, 0.45],
            }),
          },
        ]}
      />
    </View>
  );
}

function RetryIcon({ size = 12, color = '#FFFFFF' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"
        stroke={color}
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <Path
        d="M3 3v5h5"
        stroke={color}
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

function EditIcon({ size = 12, color = '#FFFFFF' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"
        stroke={color}
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

function TrashIcon({ size = 14, color = '#EF4444' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M10 11v6M14 11v6"
        stroke={color}
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

function CopyIcon({ size = 14, color = '#FFFFFF' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Rect
        x="9"
        y="9"
        width="13"
        height="13"
        rx="2"
        ry="2"
        stroke={color}
        strokeWidth="2"
      />
      <Path
        d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"
        stroke={color}
        strokeWidth="2"
      />
    </Svg>
  );
}

interface ChatMessage {
  id: string;
  sender: 'user' | 'bot';
  text: string;
  timestamp: string;
  isFailed?: boolean;
  variants?: string[];
  activeVariantIndex?: number;
}

interface ChatMessageBubbleProps {
  item: ChatMessage;
  isLastUserMsg: boolean;
  currentPersonaName: string;
  currentPersonaImage?: string;
  borderColor: string;
  onLongPress: (item: ChatMessage) => void;
  onPressFailed: (item: ChatMessage) => void;
  onOpenDetails: () => void;
  onSwitchVariant: (botMessageId: string, targetIndex: number) => void;
}

const ChatMessageBubble = React.memo(
  function ChatMessageBubble({
    item,
    isLastUserMsg,
    currentPersonaName,
    currentPersonaImage,
    borderColor,
    onLongPress,
    onPressFailed,
    onOpenDetails,
    onSwitchVariant,
  }: ChatMessageBubbleProps) {
    const isUser = item.sender === 'user';
    const variantsList = item.variants ?? [];
    const variantCount = variantsList.length;
    const currentVariantIdx =
      item.activeVariantIndex ?? (variantCount > 0 ? variantCount - 1 : 0);
    return (
      <View
        style={[
          styles.messageBubbleRow,
          isUser ? styles.userBubbleRow : styles.botBubbleRow,
        ]}
      >
        {isUser ? (
          <TouchableOpacity
            activeOpacity={0.88}
            delayLongPress={260}
            onLongPress={() => onLongPress(item)}
            onPress={() => {
              if (isLastUserMsg && item.isFailed) {
                onPressFailed(item);
              }
            }}
            style={[styles.bubbleContainer, styles.userBubble]}
          >
            <MarkdownText
              content={item.text}
              style={styles.userBubbleText}
              actionStyle={styles.userActionText}
            />
            <View style={[styles.bubbleFooterRow, styles.bubbleFooterRowDefault]}>
              {item.isFailed && (
                <View style={styles.failedIndicatorRow}>
                  <View style={styles.failedDot} />
                  <Text style={styles.failedText}>Failed</Text>
                </View>
              )}
              <Text style={[styles.bubbleTimestamp, styles.userTimestampText]}>
                {item.timestamp}
              </Text>
            </View>
          </TouchableOpacity>
        ) : (
          <View style={styles.botMessageWrapper}>
            {/* Persona Header Chip */}
            <TouchableOpacity
              style={styles.botHeaderChip}
              activeOpacity={0.8}
              onPress={onOpenDetails}
            >
              {currentPersonaImage ? (
                <Image
                  source={{ uri: currentPersonaImage }}
                  style={styles.chipAvatar}
                  fadeDuration={0}
                />
              ) : (
                <View
                  style={[
                    styles.chipAvatar,
                    styles.chipAvatarFallback,
                    { backgroundColor: borderColor },
                  ]}
                >
                  <Text style={styles.chipLetter}>
                    {cleanPersonaChipName(currentPersonaName).charAt(0).toUpperCase()}
                  </Text>
                </View>
              )}
              <Text style={styles.chipName} numberOfLines={1}>
                {cleanPersonaChipName(currentPersonaName)}
              </Text>
            </TouchableOpacity>

            {/* Wide Bot Response (No Speech Bubble, Full Width) */}
            <TouchableOpacity
              activeOpacity={0.88}
              delayLongPress={260}
              onLongPress={() => onLongPress(item)}
              style={styles.botBubble}
            >
              <MarkdownText
                content={item.text}
                style={styles.botBubbleText}
                actionStyle={styles.botActionText}
              />
              <View style={[styles.bubbleFooterRow, styles.bubbleFooterRowBot]}>
                <Text style={styles.botTimestampText}>{item.timestamp}</Text>
              </View>
            </TouchableOpacity>

            {variantCount > 1 && (
              <View style={styles.variantNavRow}>
                <TouchableOpacity
                  style={[
                    styles.variantRectBtn,
                    currentVariantIdx === 0 && styles.variantRectBtnDisabled,
                  ]}
                  onPress={() =>
                    onSwitchVariant(item.id, currentVariantIdx - 1)
                  }
                  disabled={currentVariantIdx === 0}
                  activeOpacity={0.7}
                  hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                  accessibilityLabel="Previous response"
                >
                  <Text
                    style={[
                      styles.variantArrowText,
                      currentVariantIdx === 0 && styles.variantArrowTextDisabled,
                    ]}
                  >
                    {'<'}
                  </Text>
                </TouchableOpacity>

                <Text style={styles.variantCounterText}>
                  {currentVariantIdx + 1} / {variantCount}
                </Text>

                <TouchableOpacity
                  style={[
                    styles.variantRectBtn,
                    currentVariantIdx >= variantCount - 1 &&
                      styles.variantRectBtnDisabled,
                  ]}
                  onPress={() =>
                    onSwitchVariant(item.id, currentVariantIdx + 1)
                  }
                  disabled={currentVariantIdx >= variantCount - 1}
                  activeOpacity={0.7}
                  hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                  accessibilityLabel="Next response"
                >
                  <Text
                    style={[
                      styles.variantArrowText,
                      currentVariantIdx >= variantCount - 1 &&
                        styles.variantArrowTextDisabled,
                    ]}
                  >
                    {'>'}
                  </Text>
                </TouchableOpacity>
              </View>
            )}
          </View>
        )}
      </View>
    );
  },
  (prev, next) => {
    return (
      prev.item.id === next.item.id &&
      prev.item.text === next.item.text &&
      prev.item.timestamp === next.item.timestamp &&
      prev.item.isFailed === next.item.isFailed &&
      prev.item.activeVariantIndex === next.item.activeVariantIndex &&
      prev.item.variants?.length === next.item.variants?.length &&
      prev.isLastUserMsg === next.isLastUserMsg &&
      prev.currentPersonaName === next.currentPersonaName &&
      prev.currentPersonaImage === next.currentPersonaImage &&
      prev.borderColor === next.borderColor
    );
  }
);

interface CompanionChatModalProps {
  visible: boolean;
  persona: PersonaItem | null;
  onClose: () => void;
}

async function resolveConversationUserId(userId?: string): Promise<string> {
  if (userId) return userId;

  try {
    const raw = await AsyncStorage.getItem('@amour_user_session');
    const storedUser = raw ? JSON.parse(raw) : null;
    if (storedUser?.id) return String(storedUser.id);
  } catch (err) {
    console.warn('[CompanionChat] Saved session lookup failed:', err);
  }

  return 'guest';
}

export default function CompanionChatModal({
  visible,
  persona,
  onClose,
}: CompanionChatModalProps) {
  const { user } = useAuth();
  const [activePersona, setActivePersona] = useState<PersonaItem | null>(persona);
  const [modalVisible, setModalVisible] = useState<boolean>(visible);
  const slideAnim = useRef(new Animated.Value(width)).current;
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState<string>('');
  const [isTyping, setIsTyping] = useState<boolean>(false);
  const [keyboardHeight, setKeyboardHeight] = useState<number>(0);
  const [isLoadingHistory, setIsLoadingHistory] = useState<boolean>(false);
  const [historyLoadError, setHistoryLoadError] = useState<boolean>(false);
  const [isLoadingMore, setIsLoadingMore] = useState<boolean>(false);
  const [hasMoreHistory, setHasMoreHistory] = useState<boolean>(false);
  const [isInitialScrollComplete, setIsInitialScrollComplete] = useState<boolean>(false);
  const [historyPage, setHistoryPage] = useState<number>(1);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState<boolean>(false);
  const [isPreviewImageOpen, setIsPreviewImageOpen] = useState<boolean>(false);
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null);
  const [actionMenuMessage, setActionMenuMessage] = useState<ChatMessage | null>(null);
  const [copiedToast, setCopiedToast] = useState<boolean>(false);
  const flatListRef = useRef<FlatList>(null);
  const pendingInitialScrollRef = useRef<boolean>(false);
  const initialScrollFrameRef = useRef<number | null>(null);
  const contentHeightRef = useRef<number>(0);
  const chatInputRef = useRef<any>(null);
  const spinAnim = useRef(new Animated.Value(0)).current;

  const cancelInitialScroll = React.useCallback(() => {
    pendingInitialScrollRef.current = false;
    if (initialScrollFrameRef.current !== null) {
      cancelAnimationFrame(initialScrollFrameRef.current);
      initialScrollFrameRef.current = null;
    }
  }, []);

  const handleMessagesContentSizeChange = React.useCallback((_width: number, height: number) => {
    contentHeightRef.current = height;
    if (!pendingInitialScrollRef.current || initialScrollFrameRef.current !== null) return;

    let lastHeight = -1;
    let stableFrames = 0;
    const scrollAsContentSettles = () => {
      if (!pendingInitialScrollRef.current) {
        initialScrollFrameRef.current = null;
        return;
      }

      flatListRef.current?.scrollToEnd({ animated: false });
      if (contentHeightRef.current === lastHeight) {
        stableFrames += 1;
      } else {
        lastHeight = contentHeightRef.current;
        stableFrames = 0;
      }

      if (stableFrames >= 2) {
        pendingInitialScrollRef.current = false;
        initialScrollFrameRef.current = null;
        setIsInitialScrollComplete(true);
        return;
      }

      initialScrollFrameRef.current = requestAnimationFrame(scrollAsContentSettles);
    };

    initialScrollFrameRef.current = requestAnimationFrame(scrollAsContentSettles);
  }, []);

  useEffect(() => () => {
    if (initialScrollFrameRef.current !== null) {
      cancelAnimationFrame(initialScrollFrameRef.current);
    }
  }, []);

  // iOS-style Horizontal Screen Slide Transition Controller
  useEffect(() => {
    if (visible) {
      setModalVisible(true);
      slideAnim.setValue(width);
      Animated.timing(slideAnim, {
        toValue: 0,
        duration: 360, // Silky smooth iOS push duration
        easing: Easing.bezier(0.25, 0.1, 0.25, 1), // Authentic iOS slide curve
        useNativeDriver: true,
      }).start();
    } else if (modalVisible) {
      Animated.timing(slideAnim, {
        toValue: width,
        duration: 300, // Smooth iOS pop duration
        easing: Easing.bezier(0.25, 0.1, 0.25, 1),
        useNativeDriver: true,
      }).start(() => {
        setModalVisible(false);
      });
    }
  }, [visible]);

  const handleDismiss = () => {
    Animated.timing(slideAnim, {
      toValue: width,
      duration: 300,
      easing: Easing.bezier(0.25, 0.1, 0.25, 1),
      useNativeDriver: true,
    }).start(() => {
      onClose();
    });
  };

  const handleStartEdit = (item: ChatMessage) => {
    setActionMenuMessage(null);
    setEditingMessageId(item.id);
    setInputText(item.text);
    setTimeout(() => {
      chatInputRef.current?.focus();
    }, 60);
  };

  const handleCancelEdit = () => {
    setEditingMessageId(null);
    setInputText('');
  };

  const handleCopyMessage = async (text: string) => {
    setActionMenuMessage(null);
    try {
      await Clipboard.setStringAsync(text);
      try {
        Vibration.vibrate(20);
      } catch {}
      setCopiedToast(true);
      setTimeout(() => {
        setCopiedToast(false);
      }, 2000);
    } catch (err) {
      console.warn('Failed to copy to clipboard', err);
    }
  };

  const handleSaveEditedBotResponse = async (msgId: string, newText: string) => {
    const currentPersona = activePersona || persona;
    if (!newText.trim() || !currentPersona) return;
    const trimmed = newText.trim();
    setEditingMessageId(null);
    setInputText('');

    const targetMsg = messages.find((m) => m.id === msgId);
    if (!targetMsg) return;

    const previousMessages = [...messages];

    // Optimistically update the message in local state
    setMessages((prev) =>
      prev.map((m) => {
        if (m.id === msgId) {
          const activeIdx = m.activeVariantIndex ?? (m.variants && m.variants.length > 0 ? m.variants.length - 1 : 0);
          let updatedVariants = m.variants ? [...m.variants] : undefined;
          if (updatedVariants && updatedVariants.length > 0 && activeIdx >= 0 && activeIdx < updatedVariants.length) {
            updatedVariants[activeIdx] = trimmed;
          }
          return {
            ...m,
            text: trimmed,
            variants: updatedVariants,
          };
        }
        return m;
      })
    );

    try {
      const uId = await resolveConversationUserId(user?.id);
      const res = await editBotChatMessage(msgId, trimmed, uId, user?.token);
      if (!res.success) {
        setMessages(previousMessages);
        showAlert(
          'Edit Failed',
          res.error || 'Could not update response in memory.',
          [{ text: 'OK', style: 'primary' }],
          'danger'
        );
      } else if (res.variants) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === msgId
              ? {
                  ...m,
                  text: res.text || trimmed,
                  variants: res.variants,
                  activeVariantIndex: m.activeVariantIndex,
                }
              : m
          )
        );
      }
    } catch (err: any) {
      setMessages(previousMessages);
      showAlert(
        'Edit Failed',
        err?.message || 'Network error updating response.',
        [{ text: 'OK', style: 'primary' }],
        'danger'
      );
    }
  };

  const handleDeleteMessage = (item: ChatMessage) => {
    setActionMenuMessage(null);

    showAlert(
      'Delete Message',
      'Are you sure you want to delete this message? This action cannot be undone.',
      [
        {
          text: 'Cancel',
          style: 'cancel',
        },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            const previousMessages = [...messages];
            setMessages((prev) => prev.filter((m) => m.id !== item.id));

            try {
              const uId = await resolveConversationUserId(user?.id);
              const res = await deleteChatMessage(item.id, uId, user?.token);
              if (!res.success) {
                setMessages(previousMessages);
                showAlert(
                  'Delete Failed',
                  res.error || 'Could not delete message. Please try again.',
                  [{ text: 'OK', style: 'primary' }],
                  'danger'
                );
              }
            } catch (err: any) {
              setMessages(previousMessages);
              showAlert(
                'Delete Failed',
                err?.message || 'Network error while deleting message.',
                [{ text: 'OK', style: 'primary' }],
                'danger'
              );
            }
          },
        },
      ],
      'warning'
    );
  };

  const handleSwitchVariant = React.useCallback(
    async (messageId: string, targetIndex: number) => {
      const targetMsg = messages.find((m) => m.id === messageId);
      if (!targetMsg || !targetMsg.variants || targetIndex < 0 || targetIndex >= targetMsg.variants.length) {
        return;
      }

      try {
        Vibration.vibrate(15);
      } catch {}

      const selectedText = targetMsg.variants[targetIndex];

      // Optimistic UI update: switch immediately on screen
      setMessages((prev) =>
        prev.map((m) => {
          if (m.id === messageId) {
            return {
              ...m,
              text: selectedText,
              activeVariantIndex: targetIndex,
            };
          }
          return m;
        })
      );

      // Persist selected response to PostgreSQL backend
      try {
        const uId = await resolveConversationUserId(user?.id);
        await switchChatMessageVariant(messageId, targetIndex, uId, user?.token);
      } catch (err) {
        console.warn('[CompanionChat] switchChatMessageVariant network error:', err);
      }
    },
    [messages, user?.id, user?.token]
  );

  const handleRegenerateBotReply = async (botMsg: ChatMessage) => {
    const currentPersona = activePersona || persona;
    if (isTyping || !currentPersona) return;

    const botIdx = messages.findIndex((m) => m.id === botMsg.id);
    if (botIdx === -1) return;

    let precedingUserMsg: ChatMessage | null = null;
    for (let i = botIdx - 1; i >= 0; i--) {
      if (messages[i].sender === 'user') {
        precedingUserMsg = messages[i];
        break;
      }
    }

    const textToPrompt = precedingUserMsg ? precedingUserMsg.text : currentPersona.greeting;
    const userMsgId = precedingUserMsg ? precedingUserMsg.id : undefined;

    setIsTyping(true);
    setTimeout(() => {
      flatListRef.current?.scrollToEnd({ animated: true });
    }, 80);

    const clientTime = new Date().toLocaleString('en-US', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
    const clientTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Kolkata';
    const userDisplayName = (user?.name ? user.name.trim().split(' ')[0] : '') || user?.given_name || user?.name || '';

    try {
      const conversationUserId = await resolveConversationUserId(user?.id);
      const data = await sendChatMessage(
        {
          client_message_id: `regen-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`,
          regenerate_bot_message_id: botMsg.id,
          edit_message_id: userMsgId,
          message: textToPrompt,
          persona_id: currentPersona.id,
          persona_name: currentPersona.name,
          greeting: currentPersona.greeting,
          memory_prompt: currentPersona.memory_prompt,
          client_time: clientTime,
          client_timezone: clientTimezone,
          user_id: conversationUserId,
          user_name: userDisplayName,
        },
        user?.token
      );

      if (data?.reply) {
        setMessages((prev) =>
          prev.map((m) => {
            if (m.id === botMsg.id) {
              const prevVariants = m.variants || [m.text];
              const newVariants = data.variants || [...prevVariants, data.reply];
              return {
                ...m,
                text: data.reply,
                variants: newVariants,
                activeVariantIndex: data.active_variant_index ?? newVariants.length - 1,
              };
            }
            return m;
          })
        );
      } else {
        showAlert(
          'Regeneration Failed',
          'Could not regenerate response from companion. Please try again.',
          [{ text: 'OK', style: 'primary' }],
          'warning'
        );
      }
    } catch (err) {
      console.warn('[CompanionChat] Regeneration error:', err);
      showAlert('Error', 'Network error regenerating response.', [{ text: 'OK' }], 'warning');
    } finally {
      setIsTyping(false);
    }
  };

  // Spin animation for retry icon during message sending
  useEffect(() => {
    if (isTyping) {
      const loop = Animated.loop(
        Animated.timing(spinAnim, {
          toValue: 1,
          duration: 900,
          easing: Easing.linear,
          useNativeDriver: true,
        })
      );
      loop.start();
      return () => {
        loop.stop();
        spinAnim.setValue(0);
      };
    } else {
      spinAnim.setValue(0);
    }
  }, [isTyping, spinAnim]);

  const spinInterpolate = spinAnim.interpolate({
    inputRange: [0, 1],
    outputRange: ['0deg', '360deg'],
  });

  // Identify the most recent message sent by the user for retry button attachment
  const lastUserMessageId = React.useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].sender === 'user') {
        return messages[i].id;
      }
    }
    return null;
  }, [messages]);

  // Dynamic keyboard tracker that elevates the input box perfectly above the keyboard
  useEffect(() => {
    const showEvent = Platform.OS === 'ios' ? 'keyboardWillShow' : 'keyboardDidShow';
    const hideEvent = Platform.OS === 'ios' ? 'keyboardWillHide' : 'keyboardDidHide';

    const showSub = Keyboard.addListener(showEvent, (e) => {
      setKeyboardHeight(e.endCoordinates.height);
      setTimeout(() => {
        flatListRef.current?.scrollToEnd({ animated: true });
      }, 60);
    });

    const hideSub = Keyboard.addListener(hideEvent, () => {
      setKeyboardHeight(0);
    });

    return () => {
      showSub.remove();
      hideSub.remove();
    };
  }, []);

  const loadHistory = React.useCallback(async () => {
    if (!persona?.id) return;
    setIsLoadingHistory(true);
    setIsInitialScrollComplete(false);
    setHistoryLoadError(false);
    try {
      const uId = await resolveConversationUserId(user?.id);

      const data = await fetchChatHistory(persona.id, uId, 1, 30, user?.token);

      if (data && Array.isArray(data.results)) {
        const loaded: ChatMessage[] = data.results.map((item) => ({
          id: item.id,
          sender: item.sender,
          text: item.text,
          timestamp: item.created_at
            ? new Date(item.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            : new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          isFailed: false,
          variants: item.variants || (item.response_metadata?.variants && item.response_metadata.variants.length > 1 ? item.response_metadata.variants : undefined),
          activeVariantIndex: item.active_variant_index ?? item.response_metadata?.active_variant_index ?? undefined,
        }));
        pendingInitialScrollRef.current = loaded.length > 0;
        setIsInitialScrollComplete(loaded.length === 0);
        setMessages(loaded);
        setHasMoreHistory(Boolean(data.has_more));
        setHistoryLoadError(false);
      } else {
        setHistoryLoadError(true);
      }
    } catch (err) {
      console.warn('[CompanionChat] History read error:', err);
      setHistoryLoadError(true);
    } finally {
      if (!pendingInitialScrollRef.current) {
        setIsInitialScrollComplete(true);
      }
      setIsLoadingHistory(false);
    }
  }, [persona?.id, user?.id, user?.token]);

  // Fetch paginated chat history for this (user_id, persona_id) conversation
  useEffect(() => {
    if (!visible || !persona) {
      cancelInitialScroll();
      setMessages([]);
      setEditingMessageId(null);
      setActionMenuMessage(null);
      return;
    }

    setActivePersona(persona);
    getPersonaCustomization(persona.id, user?.id).then((custom) => {
      if (custom) {
        setActivePersona((prev) => (prev ? { ...prev, ...custom } : persona));
      }
    });
    cancelInitialScroll();
    setMessages([]);
    setEditingMessageId(null);
    setActionMenuMessage(null);
    setHistoryPage(1);
    setHasMoreHistory(false);
    loadHistory();
  }, [visible, persona, loadHistory, cancelInitialScroll]);

  const handleLoadEarlier = async () => {
    if (isLoadingMore || !hasMoreHistory || !activePersona) return;
    setIsLoadingMore(true);
    const nextPage = historyPage + 1;
    try {
      const uId = await resolveConversationUserId(user?.id);
      const data = await fetchChatHistory(activePersona.id, uId, nextPage, 30, user?.token);
      if (data?.results && Array.isArray(data.results) && data.results.length > 0) {
        const older: ChatMessage[] = data.results.map((item) => ({
          id: item.id,
          sender: item.sender,
          text: item.text,
          timestamp: item.created_at
            ? new Date(item.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            : new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          isFailed: false,
          variants: item.variants || (item.response_metadata?.variants && item.response_metadata.variants.length > 1 ? item.response_metadata.variants : undefined),
          activeVariantIndex: item.active_variant_index ?? item.response_metadata?.active_variant_index ?? undefined,
        }));
        const olderCount = older.length;
        setMessages((prev) => [...older, ...prev]);
        setHistoryPage(nextPage);
        setHasMoreHistory(Boolean(data.has_more));
        setTimeout(() => {
          try {
            flatListRef.current?.scrollToIndex({
              index: olderCount,
              animated: false,
              viewPosition: 0,
            });
          } catch {}
        }, 50);
      } else {
        setHasMoreHistory(false);
      }
    } catch (err) {
      console.warn('[CompanionChat] Earlier messages load error:', err);
    } finally {
      setIsLoadingMore(false);
    }
  };

  const handleSend = async (messageTextOverride?: string, targetMessageId?: string) => {
    const text = (messageTextOverride !== undefined ? messageTextOverride : inputText).trim();
    const currentPersona = activePersona || persona;
    if (!currentPersona || isTyping) return;

    const inPlaceTargetId = targetMessageId || editingMessageId;
    const targetMsg = inPlaceTargetId ? messages.find((m) => m.id === inPlaceTargetId) : null;

    // Check if user is editing a bot/persona response: save directly in-place without generating a new reply
    if (targetMsg && targetMsg.sender === 'bot') {
      if (!text) return;
      handleSaveEditedBotResponse(targetMsg.id, text);
      return;
    }

    const isInPlace = Boolean(inPlaceTargetId);

    // If text is empty and editing an existing message, don't trigger autonomous continue
    if (!text && isInPlace) return;

    const isAutonomousContinue = !text;

    if (messageTextOverride === undefined) {
      setInputText('');
      setEditingMessageId(null);
    }

    const clientMsgId = `client-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;

    if (!isAutonomousContinue) {
      const userMsg: ChatMessage = {
        id: clientMsgId,
        sender: 'user',
        text,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        isFailed: false,
      };

      setMessages((prev) => {
        if (isInPlace && inPlaceTargetId) {
          const targetIdx = prev.findIndex((m) => m.id === inPlaceTargetId);
          if (targetIdx !== -1) {
            // Update the target message in-place and remove any subsequent bot reply while regenerating
            const updatedMsg: ChatMessage = {
              ...prev[targetIdx],
              text,
              isFailed: false,
            };
            return [...prev.slice(0, targetIdx), updatedMsg];
          }
        }
        // If retrying a message that failed at the tail of messages, replace the failed entry with the new attempt
        if (prev.length > 0 && prev[prev.length - 1].isFailed && prev[prev.length - 1].text === text) {
          return [...prev.slice(0, prev.length - 1), userMsg];
        }
        return [...prev, userMsg];
      });
    }

    setIsTyping(true);

    setTimeout(() => {
      flatListRef.current?.scrollToEnd({ animated: true });
    }, 80);

    const clientTime = new Date().toLocaleString('en-US', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
    const clientTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Kolkata';
    const userDisplayName = (user?.name ? user.name.trim().split(' ')[0] : '') || user?.given_name || user?.name || '';

    try {
      const conversationUserId = await resolveConversationUserId(user?.id);
      const data = await sendChatMessage(
        {
          client_message_id: clientMsgId,
          edit_message_id: isInPlace && inPlaceTargetId ? inPlaceTargetId : undefined,
          message: text,
          is_autonomous_continue: isAutonomousContinue,
          persona_id: currentPersona.id,
          persona_name: currentPersona.name,
          greeting: currentPersona.greeting,
          memory_prompt: currentPersona.memory_prompt,
          client_time: clientTime,
          client_timezone: clientTimezone,
          user_id: conversationUserId,
          user_name: userDisplayName,
        },
        user?.token
      );

      if (data?.reply) {
        setMessages((prev) => {
          const hasBotMatch = prev.some((m) => m.id === data.id);
          if (hasBotMatch) {
            return prev.map((m) => {
              if (m.id === data.id) {
                const newVariants = data.variants || (m.variants ? [...m.variants, data.reply] : [m.text, data.reply]);
                return {
                  ...m,
                  text: data.reply,
                  variants: newVariants,
                  activeVariantIndex: data.active_variant_index ?? newVariants.length - 1,
                };
              }
              return m;
            });
          }
          const botReply: ChatMessage = {
            id: data.id || `bot-${Date.now()}`,
            sender: 'bot',
            text: data.reply,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            variants: data.variants,
            activeVariantIndex: data.active_variant_index,
          };
          return [...prev, botReply];
        });
      } else {
        if (!isAutonomousContinue) {
          setMessages((prev) =>
            prev.map((m) => (m.id === (isInPlace && inPlaceTargetId ? inPlaceTargetId : clientMsgId) ? { ...m, isFailed: true } : m))
          );
        }
        showAlert(
          'Response Unavailable',
          'Could not receive a response from companion. Please try again.',
          [{ text: 'OK', style: 'primary' }],
          'warning'
        );
      }
    } catch (err) {
      console.warn('[CompanionChat] Send error:', err);
      if (!isAutonomousContinue) {
        setMessages((prev) =>
          prev.map((m) => (m.id === (isInPlace && inPlaceTargetId ? inPlaceTargetId : clientMsgId) ? { ...m, isFailed: true } : m))
        );
      }
      showAlert(
        'Connection Issue',
        'Failed to deliver message. Please check your network connection.',
        [{ text: 'OK', style: 'primary' }],
        'warning'
      );
    } finally {
      setIsTyping(false);
      setTimeout(() => {
        flatListRef.current?.scrollToEnd({ animated: true });
      }, 100);
    }
  };

  const currentPersona = activePersona || persona;
  const currentPersonaName = currentPersona?.name || 'Companion';
  const currentPersonaImage = currentPersona?.image_url;
  const borderColor = currentPersona?.border_color || '#F43F5E';

  const keyExtractor = React.useCallback((item: ChatMessage) => item.id, []);

  const handleLongPressMessage = React.useCallback((item: ChatMessage) => {
    try {
      Vibration.vibrate(25);
    } catch {}
    setActionMenuMessage(item);
  }, []);

  const handlePressFailedMessage = React.useCallback((item: ChatMessage) => {
    try {
      Vibration.vibrate(20);
    } catch {}
    setActionMenuMessage(item);
  }, []);

  const handleOpenDetails = React.useCallback(() => {
    setIsDetailModalOpen(true);
  }, []);

  const renderItem = React.useCallback(
    ({ item }: { item: ChatMessage }) => {
      const isUser = item.sender === 'user';
      const isLastUserMsg = isUser && item.id === lastUserMessageId;
      return (
        <ChatMessageBubble
          item={item}
          isLastUserMsg={isLastUserMsg}
          currentPersonaName={currentPersonaName}
          currentPersonaImage={currentPersonaImage}
          borderColor={borderColor}
          onLongPress={handleLongPressMessage}
          onPressFailed={handlePressFailedMessage}
          onOpenDetails={handleOpenDetails}
          onSwitchVariant={handleSwitchVariant}
        />
      );
    },
    [
      lastUserMessageId,
      currentPersonaName,
      currentPersonaImage,
      borderColor,
      handleLongPressMessage,
      handlePressFailedMessage,
      handleOpenDetails,
      handleSwitchVariant,
    ]
  );

  const backdropOpacity = slideAnim.interpolate({
    inputRange: [0, width],
    outputRange: [0.65, 0],
    extrapolate: 'clamp',
  });

  if (!visible && !modalVisible) return null;
  if (!currentPersona) return null;

  return (
    <>
      <Modal
        visible={modalVisible}
        transparent={true}
        animationType="none"
        statusBarTranslucent={true}
        onRequestClose={handleDismiss}
      >
      <View style={styles.modalRoot}>
        {/* iOS Dimming Backdrop over previous screen */}
        <Animated.View
          style={[
            StyleSheet.absoluteFill,
            { backgroundColor: '#000000', opacity: backdropOpacity },
          ]}
          pointerEvents="none"
        />

        {/* Smooth iOS Horizontal Sliding Screen */}
        <Animated.View
          style={[
            styles.slideContainer,
            { transform: [{ translateX: slideAnim }] },
          ]}
        >
          <SafeAreaView style={styles.safeArea} edges={['top', 'bottom']}>
            {/* Top Header */}
            <View style={styles.topHeader}>
              <TouchableOpacity
                onPress={handleDismiss}
                style={styles.backBtn}
                activeOpacity={0.7}
                hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
                accessibilityLabel="Back to companions"
              >
                <BackIcon size={20} color="#FFFFFF" />
              </TouchableOpacity>

          <View style={styles.headerProfileCol}>
            {/* Persona DP / Avatar - Tap to View Netflix-Paused Image Preview */}
            <TouchableOpacity
              style={[styles.headerSquircle, { borderColor }]}
              onPress={() => setIsPreviewImageOpen(true)}
              activeOpacity={0.8}
              accessibilityLabel={`View photo of ${currentPersona.name}`}
            >
              {currentPersona.image_url ? (
                <Image source={{ uri: currentPersona.image_url }} style={styles.headerAvatarImg} fadeDuration={0} />
              ) : (
                <View style={[styles.headerAvatarImg, { backgroundColor: borderColor }]}>
                  <Text style={styles.headerAvatarLetter}>
                    {(cleanPersonaChipName(currentPersona.name).charAt(0) || 'C').toUpperCase()}
                  </Text>
                </View>
              )}
            </TouchableOpacity>

            {/* Persona Details - Tap to Open Persona Details Profile */}
            <TouchableOpacity
              style={styles.headerTextCol}
              onPress={() => setIsDetailModalOpen(true)}
              activeOpacity={0.7}
              accessibilityLabel={`View profile details of ${cleanPersonaChipName(currentPersona.name)}`}
            >
              <View style={styles.nameWithBadgeRow}>
                <Text style={styles.headerBotName} numberOfLines={1}>{cleanPersonaChipName(currentPersona.name)}{currentPersona.age ? `, ${currentPersona.age}` : ''}</Text>
                <View style={styles.headerInfoPill}>
                  <Text style={styles.headerInfoText}>i</Text>
                </View>
              </View>
            </TouchableOpacity>
          </View>

          {/* Header Menu Button */}
          <TouchableOpacity
            style={styles.menuBtn}
            onPress={() => setIsDetailModalOpen(true)}
            activeOpacity={0.7}
            hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
            accessibilityLabel="Persona details menu"
          >
            <MenuIcon size={18} color="#FFFFFF" />
          </TouchableOpacity>
        </View>

        {/* Messages Flow */}
        <FlatList
          ref={flatListRef}
          data={messages}
          onContentSizeChange={handleMessagesContentSizeChange}
          renderItem={renderItem}
          keyExtractor={keyExtractor}
          extraData={lastUserMessageId}
          removeClippedSubviews={Platform.OS === 'android'}
          maxToRenderPerBatch={10}
          windowSize={11}
          initialNumToRender={14}
          updateCellsBatchingPeriod={40}
          contentContainerStyle={[
            styles.messagesList,
            messages.length === 0 && styles.emptyMessagesList,
          ]}
          keyboardShouldPersistTaps="handled"
          maintainVisibleContentPosition={
            Platform.OS === 'ios'
              && isInitialScrollComplete
              ? { minIndexForVisible: 0 }
              : undefined
          }
          onScrollToIndexFailed={() => {}}
          ListHeaderComponent={
            hasMoreHistory ? (
              <TouchableOpacity
                style={styles.loadEarlierBtn}
                onPress={handleLoadEarlier}
                disabled={isLoadingMore}
                activeOpacity={0.7}
              >
                {isLoadingMore ? (
                  <ActivityIndicator size="small" color="#9CA3AF" />
                ) : (
                  <Text style={styles.loadEarlierText}>Load earlier messages</Text>
                )}
              </TouchableOpacity>
            ) : undefined
          }
          ListEmptyComponent={
            isLoadingHistory ? (
              <View style={styles.emptyContainer}>
                <ActivityIndicator size="small" color={borderColor} />
                <Text style={[styles.emptyHintText, { marginTop: 12 }]}>Restoring conversation...</Text>
              </View>
            ) : historyLoadError ? (
              <View style={styles.emptyContainer}>
                <Text style={{ fontSize: 26, marginBottom: 8 }}>⚠️</Text>
                <Text style={[styles.emptyPersonaName, { fontSize: 15 }]}>Unable to connect</Text>
                <Text style={[styles.emptyTagline, { color: '#9CA3AF', marginTop: 4, maxWidth: 280, textAlign: 'center' }]}>
                  Your encrypted chat history is safely preserved on the server.
                </Text>
                <TouchableOpacity
                  onPress={loadHistory}
                  style={{
                    marginTop: 16,
                    paddingHorizontal: 20,
                    paddingVertical: 9,
                    backgroundColor: 'rgba(255, 255, 255, 0.12)',
                    borderRadius: 20,
                    borderWidth: 1,
                    borderColor: 'rgba(255, 255, 255, 0.25)',
                  }}
                  activeOpacity={0.7}
                >
                  <Text style={{ color: '#FFFFFF', fontSize: 13, fontWeight: '600' }}>Tap to Retry</Text>
                </TouchableOpacity>
              </View>
            ) : (
              <View style={styles.emptyContainer}>
                <View style={[styles.emptySquircle, { borderColor }]}>
                  {currentPersona.image_url ? (
                    <Image source={{ uri: currentPersona.image_url }} style={styles.emptyAvatarImg} fadeDuration={0} />
                  ) : (
                    <View style={[styles.emptyAvatarFallback, { backgroundColor: borderColor }]}>
                      <Text style={styles.emptyAvatarLetter}>{cleanPersonaChipName(currentPersona.name).charAt(0)}</Text>
                    </View>
                  )}
                </View>
                <Text style={styles.emptyPersonaName}>{cleanPersonaChipName(currentPersona.name)}</Text>
                {currentPersona.greeting ? (
                  <Text style={styles.emptyTagline}>"{currentPersona.greeting}"</Text>
                ) : (
                  <Text style={styles.emptyTagline}>Always here to talk</Text>
                )}
                <Text style={styles.emptyHintText}>Send a message to start chatting</Text>
              </View>
            )
          }
          ListFooterComponent={
            isTyping ? (
              <View style={styles.typingRow}>
                {currentPersona.image_url ? (
                  <Image
                    source={{ uri: currentPersona.image_url }}
                    style={styles.typingAvatar}
                    fadeDuration={0}
                  />
                ) : (
                  <View style={[styles.typingAvatar, styles.typingAvatarFallback, { backgroundColor: borderColor }]}>
                    <Text style={styles.typingAvatarLetter}>
                      {(cleanPersonaChipName(currentPersona.name).charAt(0) || 'C').toUpperCase()}
                    </Text>
                  </View>
                )}
                <View style={styles.typingPill}>
                  <TypingDotsAnimation color="#D4D4D8" />
                </View>
              </View>
            ) : undefined
          }
        />

        {/* Bottom Floating Chat Input - Guaranteed to stay above keyboard */}
        <View
          style={[
            styles.inputContainer,
            {
              paddingBottom:
                keyboardHeight > 0
                  ? keyboardHeight + (Platform.OS === 'android' ? 6 : 4)
                  : (Platform.OS === 'ios' ? 12 : 14),
            },
          ]}
        >
          {editingMessageId && (
            <View style={styles.editingBanner}>
              <View style={styles.editingBannerLeft}>
                <EditIcon size={12} color={borderColor} />
                <Text style={styles.editingBannerText}>
                  {messages.find((m) => m.id === editingMessageId)?.sender === 'bot'
                    ? 'Editing persona response'
                    : 'Editing message'}
                </Text>
              </View>
              <TouchableOpacity
                onPress={handleCancelEdit}
                hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                style={styles.cancelEditBtn}
                accessibilityLabel="Cancel editing"
              >
                <CloseIcon size={14} color="#9CA3AF" />
              </TouchableOpacity>
            </View>
          )}

          <View style={styles.inputCapsule}>
            <View style={styles.inputUserIconWrapper}>
              <InputUserIcon size={26} />
            </View>

            <TextInput
              ref={chatInputRef}
              style={styles.chatTextInput}
              placeholder={
                editingMessageId
                  ? messages.find((m) => m.id === editingMessageId)?.sender === 'bot'
                    ? 'Edit persona response...'
                    : 'Edit your message...'
                  : 'Type a message...'
              }
              placeholderTextColor="#71717A"
              value={inputText}
              onChangeText={setInputText}
              multiline
              maxLength={1000}
            />

            <TouchableOpacity
              style={[
                styles.sendBtn,
                {
                  backgroundColor: inputText.trim() ? '#3F3F46' : '#2A2A2E',
                },
              ]}
              onPress={() => handleSend()}
              disabled={isTyping}
              activeOpacity={0.75}
              accessibilityLabel={inputText.trim() ? 'Send message' : 'Continue interaction'}
            >
              <ChatSendIcon
                size={16}
                color={inputText.trim() ? '#FFFFFF' : '#A1A1AA'}
              />
            </TouchableOpacity>
          </View>
        </View>

        {/* Copied Toast Banner */}
        {copiedToast && (
          <View style={styles.copiedToastBadge}>
            <Text style={styles.copiedToastText}>Copied to clipboard</Text>
          </View>
        )}

        {/* Floating Message Action Modal - Options Only, No Floating Message */}
        <Modal
          visible={Boolean(actionMenuMessage)}
          transparent={true}
          animationType="fade"
          onRequestClose={() => setActionMenuMessage(null)}
          statusBarTranslucent={true}
        >
          <TouchableOpacity
            style={styles.igOverlayBackdrop}
            activeOpacity={1}
            onPress={() => setActionMenuMessage(null)}
          >
            {actionMenuMessage && (
              <View
                style={styles.igActionCard}
                onStartShouldSetResponder={() => true}
              >
                {/* 1. Copy Option (Available for BOTH User message & Bot response) */}
                <TouchableOpacity
                  style={styles.igActionRow}
                  activeOpacity={0.7}
                  onPress={() => {
                    const textToCopy = actionMenuMessage.text;
                    handleCopyMessage(textToCopy);
                  }}
                >
                  <View style={styles.igActionRowLeft}>
                    <View style={styles.igActionIconCircle}>
                      <CopyIcon size={14} color="#FFFFFF" />
                    </View>
                    <Text style={styles.igActionText}>Copy</Text>
                  </View>
                </TouchableOpacity>

                <View style={styles.igActionDivider} />

                {/* 2. User-specific actions */}
                {actionMenuMessage.sender === 'user' && (
                  <>
                    <TouchableOpacity
                      style={styles.igActionRow}
                      activeOpacity={0.7}
                      onPress={() => {
                        const msg = actionMenuMessage;
                        setActionMenuMessage(null);
                        handleStartEdit(msg);
                      }}
                      disabled={isTyping}
                    >
                      <View style={styles.igActionRowLeft}>
                        <View style={styles.igActionIconCircle}>
                          <EditIcon size={14} color="#FFFFFF" />
                        </View>
                        <Text style={styles.igActionText}>Edit</Text>
                      </View>
                    </TouchableOpacity>

                    <View style={styles.igActionDivider} />

                    <TouchableOpacity
                      style={styles.igActionRow}
                      activeOpacity={0.7}
                      onPress={() => {
                        const textToSend = actionMenuMessage.text;
                        const msgId = actionMenuMessage.id;
                        setActionMenuMessage(null);
                        handleSend(textToSend, msgId);
                      }}
                      disabled={isTyping}
                    >
                      <View style={styles.igActionRowLeft}>
                        <View
                          style={[
                            styles.igActionIconCircle,
                            actionMenuMessage.isFailed && styles.igActionIconCircleFailed,
                          ]}
                        >
                          <RetryIcon size={14} color="#FFFFFF" />
                        </View>
                        <Text style={styles.igActionText}>
                          {actionMenuMessage.isFailed ? 'Retry Message' : 'Resend'}
                        </Text>
                      </View>
                    </TouchableOpacity>

                    <View style={styles.igActionDivider} />
                  </>
                )}

                {/* 3. Bot-specific actions */}
                {actionMenuMessage.sender === 'bot' && (
                  <>
                    <TouchableOpacity
                      style={styles.igActionRow}
                      activeOpacity={0.7}
                      onPress={() => {
                        const botMsg = actionMenuMessage;
                        setActionMenuMessage(null);
                        handleStartEdit(botMsg);
                      }}
                      disabled={isTyping}
                    >
                      <View style={styles.igActionRowLeft}>
                        <View style={styles.igActionIconCircle}>
                          <EditIcon size={14} color="#FFFFFF" />
                        </View>
                        <Text style={styles.igActionText}>Edit Response</Text>
                      </View>
                    </TouchableOpacity>

                    <View style={styles.igActionDivider} />

                    <TouchableOpacity
                      style={styles.igActionRow}
                      activeOpacity={0.7}
                      onPress={() => {
                        const botMsg = actionMenuMessage;
                        setActionMenuMessage(null);
                        handleRegenerateBotReply(botMsg);
                      }}
                      disabled={isTyping}
                    >
                      <View style={styles.igActionRowLeft}>
                        <View style={styles.igActionIconCircle}>
                          <RetryIcon size={14} color="#FFFFFF" />
                        </View>
                        <Text style={styles.igActionText}>Regenerate Response</Text>
                      </View>
                    </TouchableOpacity>

                    <View style={styles.igActionDivider} />
                  </>
                )}

                {/* 4. Delete Action (Available for both user and bot messages) */}
                <TouchableOpacity
                  style={styles.igActionRow}
                  activeOpacity={0.7}
                  onPress={() => {
                    const msg = actionMenuMessage;
                    handleDeleteMessage(msg);
                  }}
                  disabled={isTyping}
                >
                  <View style={styles.igActionRowLeft}>
                    <View style={[styles.igActionIconCircle, styles.igActionIconCircleDelete]}>
                      <TrashIcon size={14} color="#EF4444" />
                    </View>
                    <Text style={[styles.igActionText, styles.igActionTextDelete]}>
                      Delete Message
                    </Text>
                  </View>
                </TouchableOpacity>
              </View>
            )}
          </TouchableOpacity>
        </Modal>

        {/* Fullscreen DP / Avatar Viewer - Netflix Paused Photo Preview */}
        {isPreviewImageOpen && (
          <ImagePreviewModal
            visible={isPreviewImageOpen}
            imageUrl={currentPersona.image_url}
            name={currentPersona.name}
            tagline={currentPersona.tagline}
            borderColor={borderColor}
            onClose={() => setIsPreviewImageOpen(false)}
          />
          )}
          </SafeAreaView>
        </Animated.View>
      </View>
    </Modal>

    {/* Persona Details & Mind Profile Modal - Rendered outside parent Modal to prevent Android nested Modal collisions */}
    <PersonaDetailModal
      visible={isDetailModalOpen}
      persona={currentPersona}
      onClose={() => setIsDetailModalOpen(false)}
      onInitiateChat={() => setIsDetailModalOpen(false)}
    />
  </>
  );
}

const styles = StyleSheet.create({
  modalRoot: {
    flex: 1,
    backgroundColor: 'transparent',
  },
  slideContainer: {
    flex: 1,
    width: '100%',
    height: '100%',
    backgroundColor: '#171717',
  },
  safeArea: {
    flex: 1,
    backgroundColor: '#171717',
  },
  topHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#242426',
    backgroundColor: '#171717',
  },
  backBtn: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: '#262628',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: '#343438',
  },
  menuBtn: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: '#262628',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: '#343438',
  },
  headerProfileCol: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    flex: 1,
    marginLeft: 10,
    marginRight: 6,
  },
  headerSquircle: {
    width: 40,
    height: 40,
    borderRadius: 14,
    borderWidth: 1.8,
    overflow: 'hidden',
    backgroundColor: '#262628',
  },
  headerAvatarImg: {
    width: '100%',
    height: '100%',
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerAvatarLetter: {
    fontFamily: 'ChangaOne-Regular',
    fontSize: 18,
    color: '#FFFFFF',
  },
  headerTextCol: {
    justifyContent: 'center',
    flex: 1,
  },
  headerBotName: {
    fontFamily: 'ChangaOne-Regular',
    fontSize: 16.5,
    color: '#FFFFFF',
    letterSpacing: 0.3,
  },
  nameWithBadgeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  headerInfoPill: {
    width: 16,
    height: 16,
    borderRadius: 8,
    backgroundColor: '#262628',
    borderColor: '#343438',
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerInfoText: {
    color: '#9CA3AF',
    fontSize: 10,
    fontWeight: '700',
    fontStyle: 'italic',
    lineHeight: 12,
  },
  headerSpacer: {
    width: 38,
  },
  messagesList: {
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 20,
    gap: 12,
  },
  emptyMessagesList: {
    flexGrow: 1,
    justifyContent: 'center',
  },
  emptyContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 32,
    paddingVertical: 40,
  },
  emptySquircle: {
    width: 76,
    height: 76,
    borderRadius: 26,
    borderWidth: 2,
    overflow: 'hidden',
    backgroundColor: '#262628',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
  },
  emptyAvatarImg: {
    width: '100%',
    height: '100%',
  },
  emptyAvatarFallback: {
    width: '100%',
    height: '100%',
    alignItems: 'center',
    justifyContent: 'center',
  },
  emptyAvatarLetter: {
    fontFamily: 'ChangaOne-Regular',
    fontSize: 32,
    color: '#FFFFFF',
  },
  emptyPersonaName: {
    fontFamily: 'ChangaOne-Regular',
    fontSize: 22,
    color: '#FFFFFF',
    letterSpacing: 0.3,
    marginBottom: 8,
  },
  emptyTagline: {
    fontSize: 14,
    color: '#94A3B8',
    textAlign: 'center',
    fontStyle: 'italic',
    lineHeight: 20,
    marginBottom: 16,
    paddingHorizontal: 12,
  },
  emptyHintText: {
    fontSize: 12,
    color: '#64748B',
    fontWeight: '500',
  },
  loadEarlierBtn: {
    alignSelf: 'center',
    paddingHorizontal: 14,
    paddingVertical: 7,
    borderRadius: 14,
    backgroundColor: '#262628',
    borderWidth: 1,
    borderColor: '#343438',
    marginBottom: 10,
    marginTop: 4,
  },
  loadEarlierText: {
    fontSize: 11.5,
    color: '#9CA3AF',
    fontWeight: '500',
  },
  messageBubbleRow: {
    width: '100%',
    flexDirection: 'row',
  },
  userBubbleRow: {
    justifyContent: 'flex-end',
  },
  botBubbleRow: {
    justifyContent: 'flex-start',
  },
  bubbleContainer: {
    maxWidth: '82%',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderRadius: 20,
  },
  userBubble: {
    backgroundColor: '#323236',
    borderRadius: 18,
    borderBottomRightRadius: 4,
    borderWidth: 1,
    borderColor: '#404046',
  },
  botBubble: {
    width: '100%',
    maxWidth: '100%',
    backgroundColor: 'transparent',
    borderWidth: 0,
    paddingHorizontal: 0,
    paddingVertical: 2,
    borderRadius: 0,
  },
  botMessageWrapper: {
    width: '100%',
    maxWidth: '100%',
    alignItems: 'flex-start',
    marginVertical: 4,
  },
  botHeaderChip: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#262628',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#343438',
    paddingLeft: 4,
    paddingRight: 12,
    paddingVertical: 3,
    marginBottom: 6,
    maxWidth: '92%',
    gap: 8,
  },
  chipAvatar: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: '#1C1C20',
  },
  chipAvatarFallback: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  chipLetter: {
    fontFamily: 'ChangaOne-Regular',
    fontSize: 12,
    color: '#FFFFFF',
  },
  chipName: {
    fontSize: 13,
    fontWeight: '600',
    color: '#E4E4E7',
    letterSpacing: 0.2,
    flexShrink: 1,
  },
  typingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginTop: 6,
    marginBottom: 8,
    alignSelf: 'flex-start',
  },
  typingAvatar: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: '#262628',
  },
  typingAvatarFallback: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  typingAvatarLetter: {
    fontFamily: 'ChangaOne-Regular',
    fontSize: 14,
    color: '#FFFFFF',
  },
  typingPill: {
    backgroundColor: '#2A2A2E',
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 10,
    minHeight: 36,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#343438',
  },
  variantNavRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 8,
    backgroundColor: '#242426',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#343438',
    paddingHorizontal: 6,
    paddingVertical: 4,
    gap: 6,
  },
  variantRectBtn: {
    width: 26,
    height: 22,
    borderRadius: 4,
    backgroundColor: '#1E1E2C',
    borderWidth: 1,
    borderColor: '#303046',
    alignItems: 'center',
    justifyContent: 'center',
  },
  variantRectBtnDisabled: {
    backgroundColor: '#14141E',
    borderColor: '#20202E',
    opacity: 0.35,
  },
  variantArrowText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#D1D5DB',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    lineHeight: 14,
    textAlign: 'center',
  },
  variantArrowTextDisabled: {
    color: '#6B7280',
  },
  variantCounterText: {
    fontSize: 11,
    fontWeight: '600',
    color: '#9CA3AF',
    letterSpacing: 0.5,
    paddingHorizontal: 2,
  },
  userBubbleText: {
    fontSize: 15,
    color: '#FFFFFF',
    lineHeight: 22,
  },
  botBubbleText: {
    fontSize: 15.5,
    color: '#FFFFFF',
    lineHeight: 24,
    letterSpacing: 0.15,
  },
  userActionText: {
    fontStyle: 'italic',
    color: '#FFE4E6',
  },
  botActionText: {
    fontStyle: 'italic',
    color: '#9CA3AF',
  },
  bubbleFooterRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 6,
  },
  bubbleFooterRowDefault: {
    justifyContent: 'flex-end',
  },
  bubbleFooterRowBot: {
    justifyContent: 'flex-start',
    marginTop: 4,
  },
  failedIndicatorRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginRight: 6,
  },
  failedDot: {
    width: 5,
    height: 5,
    borderRadius: 2.5,
    backgroundColor: '#F87171',
  },
  failedText: {
    fontSize: 10,
    fontWeight: '600',
    color: '#FCA5A5',
    letterSpacing: 0.2,
  },
  copiedToastBadge: {
    position: 'absolute',
    top: 70,
    alignSelf: 'center',
    backgroundColor: '#1E1E24',
    borderColor: '#374151',
    borderWidth: 1,
    paddingHorizontal: 16,
    paddingVertical: 9,
    borderRadius: 20,
    zIndex: 9999,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.35,
    shadowRadius: 8,
    elevation: 10,
  },
  copiedToastText: {
    color: '#F9FAFB',
    fontSize: 13,
    fontWeight: '600',
    letterSpacing: 0.2,
  },
  igOverlayBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.65)',
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 24,
  },
  igActionCard: {
    width: 220,
    backgroundColor: '#1E1E22',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#2E2E34',
    overflow: 'hidden',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.55,
    shadowRadius: 14,
    elevation: 12,
  },
  igActionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 13,
  },
  igActionRowLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  igActionIconCircle: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: 'rgba(255, 255, 255, 0.08)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  igActionIconCircleFailed: {
    backgroundColor: 'rgba(239, 68, 68, 0.2)',
  },
  igActionIconCircleDelete: {
    backgroundColor: 'rgba(239, 68, 68, 0.15)',
  },
  igActionText: {
    fontSize: 14.5,
    fontWeight: '600',
    color: '#FFFFFF',
    letterSpacing: 0.2,
  },
  igActionTextDelete: {
    color: '#EF4444',
  },
  igActionDivider: {
    height: 1,
    backgroundColor: '#2E2E32',
    width: '100%',
  },
  bubbleTimestamp: {
    fontSize: 10,
  },
  editingBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 14,
    paddingVertical: 7,
    marginBottom: 6,
    backgroundColor: '#202022',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#2E2E32',
  },
  editingBannerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  editingBannerText: {
    fontSize: 12,
    color: '#D1D5DB',
    fontWeight: '500',
  },
  cancelEditBtn: {
    padding: 2,
  },
  userTimestampText: {
    color: 'rgba(255, 255, 255, 0.75)',
  },
  botTimestampText: {
    color: '#71717A',
  },
  typingBubbleContainer: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    minHeight: 38,
    justifyContent: 'center',
    alignItems: 'center',
    alignSelf: 'flex-start',
    marginTop: 2,
    marginBottom: 4,
  },
  typingDotsContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 5,
    height: 14,
  },
  typingDot: {
    width: 7,
    height: 7,
    borderRadius: 3.5,
  },
  inputContainer: {
    paddingHorizontal: 16,
    paddingTop: 8,
    backgroundColor: '#171717',
    borderTopWidth: 1,
    borderTopColor: '#242426',
  },
  inputCapsule: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#262628',
    borderRadius: 25,
    borderWidth: 1,
    borderColor: '#343438',
    paddingLeft: 8,
    paddingRight: 6,
    paddingVertical: 4,
  },
  inputUserIconWrapper: {
    marginLeft: 2,
    marginRight: 6,
    justifyContent: 'center',
    alignItems: 'center',
  },
  chatTextInput: {
    flex: 1,
    fontSize: 14.5,
    color: '#FFFFFF',
    minHeight: 38,
    maxHeight: 100,
    paddingVertical: 6,
  },
  sendBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
