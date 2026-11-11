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
import Svg, { Path, Circle } from 'react-native-svg';
import MarkdownText from './MarkdownText';
import PersonaDetailModal from './PersonaDetailModal';
import ImagePreviewModal from './ImagePreviewModal';
import { PersonaItem } from '../services/personaService';
import { fetchChatHistory, sendChatMessage } from '../services/chatService';
import { useAuth } from '../context/AuthContext';
import { showAlert } from '../context/AlertContext';
import AsyncStorage from '@react-native-async-storage/async-storage';

const { width } = Dimensions.get('window');

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

function TypingDotsAnimation({ color = '#A1A1AA' }: { color?: string }) {
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

interface ChatMessage {
  id: string;
  sender: 'user' | 'bot';
  text: string;
  timestamp: string;
  isFailed?: boolean;
}

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
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState<string>('');
  const [isTyping, setIsTyping] = useState<boolean>(false);
  const [keyboardHeight, setKeyboardHeight] = useState<number>(0);
  const [isLoadingHistory, setIsLoadingHistory] = useState<boolean>(false);
  const [historyLoadError, setHistoryLoadError] = useState<boolean>(false);
  const [isLoadingMore, setIsLoadingMore] = useState<boolean>(false);
  const [hasMoreHistory, setHasMoreHistory] = useState<boolean>(false);
  const [historyPage, setHistoryPage] = useState<number>(1);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState<boolean>(false);
  const [isPreviewImageOpen, setIsPreviewImageOpen] = useState<boolean>(false);
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null);
  const [actionMenuMessage, setActionMenuMessage] = useState<ChatMessage | null>(null);
  const flatListRef = useRef<FlatList>(null);
  const chatInputRef = useRef<any>(null);
  const spinAnim = useRef(new Animated.Value(0)).current;

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
        }));
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
      setIsLoadingHistory(false);
      setTimeout(() => flatListRef.current?.scrollToEnd({ animated: false }), 80);
    }
  }, [persona?.id, user?.id, user?.token]);

  // Fetch paginated chat history for this (user_id, persona_id) conversation
  useEffect(() => {
    if (!visible || !persona) {
      setMessages([]);
      setEditingMessageId(null);
      setActionMenuMessage(null);
      return;
    }

    setActivePersona(persona);
    setMessages([]);
    setEditingMessageId(null);
    setActionMenuMessage(null);
    setHistoryPage(1);
    setHasMoreHistory(false);
    loadHistory();
  }, [visible, persona, loadHistory]);

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
        }));
        setMessages((prev) => [...older, ...prev]);
        setHistoryPage(nextPage);
        setHasMoreHistory(Boolean(data.has_more));
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
    if (!text || !activePersona || isTyping) return;

    const inPlaceTargetId = targetMessageId || editingMessageId;
    const isInPlace = Boolean(inPlaceTargetId);

    if (messageTextOverride === undefined) {
      setInputText('');
      setEditingMessageId(null);
    }

    const clientMsgId = `client-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;

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
          persona_id: activePersona.id,
          persona_name: activePersona.name,
          greeting: activePersona.greeting,
          memory_prompt: activePersona.memory_prompt,
          client_time: clientTime,
          client_timezone: clientTimezone,
          user_id: conversationUserId,
          user_name: userDisplayName,
        },
        user?.token
      );

      if (data?.reply) {
        const botReply: ChatMessage = {
          id: data.id || `bot-${Date.now()}`,
          sender: 'bot',
          text: data.reply,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        };
        setMessages((prev) => [...prev, botReply]);
      } else {
        setMessages((prev) =>
          prev.map((m) => (m.id === (isInPlace && inPlaceTargetId ? inPlaceTargetId : clientMsgId) ? { ...m, isFailed: true } : m))
        );
        showAlert(
          'Response Unavailable',
          'Could not receive a response from companion. Please try again.',
          [{ text: 'OK', style: 'primary' }],
          'warning'
        );
      }
    } catch (err) {
      console.warn('[CompanionChat] Send error:', err);
      setMessages((prev) =>
        prev.map((m) => (m.id === (isInPlace && inPlaceTargetId ? inPlaceTargetId : clientMsgId) ? { ...m, isFailed: true } : m))
      );
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

  if (!activePersona) return null;
  const borderColor = activePersona.border_color || '#F43F5E';

  return (
    <Modal
      visible={visible}
      animationType="slide"
      statusBarTranslucent={true}
      onRequestClose={onClose}
    >
      <SafeAreaView style={styles.safeArea} edges={['top', 'bottom']}>
        {/* Top Header */}
        <View style={styles.topHeader}>
          <TouchableOpacity
            onPress={onClose}
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
              accessibilityLabel={`View photo of ${activePersona.name}`}
            >
              {activePersona.image_url ? (
                <Image source={{ uri: activePersona.image_url }} style={styles.headerAvatarImg} />
              ) : (
                <View style={[styles.headerAvatarImg, { backgroundColor: borderColor }]}>
                  <Text style={styles.headerAvatarLetter}>
                    {activePersona.name.charAt(0).toUpperCase()}
                  </Text>
                </View>
              )}
            </TouchableOpacity>

            {/* Persona Details - Tap to Open Persona Details Profile */}
            <TouchableOpacity
              style={styles.headerTextCol}
              onPress={() => setIsDetailModalOpen(true)}
              activeOpacity={0.7}
              accessibilityLabel={`View profile details of ${activePersona.name}`}
            >
              <View style={styles.nameWithBadgeRow}>
                <Text style={styles.headerBotName} numberOfLines={1}>{activePersona.name}{activePersona.age ? `, ${activePersona.age}` : ''}</Text>
                <View style={styles.headerInfoPill}>
                  <Text style={styles.headerInfoText}>i</Text>
                </View>
              </View>
              <View style={styles.statusRow}>
                <View style={styles.onlineDot} />
                <Text style={styles.headerStatusText}>Online · Details</Text>
              </View>
            </TouchableOpacity>
          </View>

          {/* Symmetrical header spacer */}
          <View style={styles.headerSpacer} />
        </View>

        {/* Messages Flow */}
        <FlatList
          ref={flatListRef}
          data={messages}
          extraData={{ lastUserMessageId, isTyping }}
          keyExtractor={(item) => item.id}
          contentContainerStyle={[
            styles.messagesList,
            messages.length === 0 && styles.emptyMessagesList,
          ]}
          keyboardShouldPersistTaps="handled"
          onContentSizeChange={() => flatListRef.current?.scrollToEnd({ animated: true })}
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
                  {activePersona.image_url ? (
                    <Image source={{ uri: activePersona.image_url }} style={styles.emptyAvatarImg} />
                  ) : (
                    <View style={[styles.emptyAvatarFallback, { backgroundColor: borderColor }]}>
                      <Text style={styles.emptyAvatarLetter}>{activePersona.name.charAt(0)}</Text>
                    </View>
                  )}
                </View>
                <Text style={styles.emptyPersonaName}>{activePersona.name}</Text>
                {activePersona.greeting ? (
                  <Text style={styles.emptyTagline}>"{activePersona.greeting}"</Text>
                ) : (
                  <Text style={styles.emptyTagline}>Always here to talk</Text>
                )}
                <Text style={styles.emptyHintText}>Send a message to start chatting</Text>
              </View>
            )
          }
          renderItem={({ item }) => {
            const isUser = item.sender === 'user';
            const isLastUserMsg = isUser && item.id === lastUserMessageId;
            return (
              <View
                style={[
                  styles.messageBubbleRow,
                  isUser ? styles.userBubbleRow : styles.botBubbleRow,
                ]}
              >
                <TouchableOpacity
                  activeOpacity={isLastUserMsg ? 0.88 : 1}
                  delayLongPress={260}
                  onLongPress={() => {
                    if (isLastUserMsg) {
                      try {
                        Vibration.vibrate(25);
                      } catch {}
                      setActionMenuMessage(item);
                    }
                  }}
                  onPress={() => {
                    if (isLastUserMsg && item.isFailed) {
                      try {
                        Vibration.vibrate(20);
                      } catch {}
                      setActionMenuMessage(item);
                    }
                  }}
                  style={[
                    styles.bubbleContainer,
                    isUser
                      ? [styles.userBubble, { backgroundColor: borderColor }]
                      : styles.botBubble,
                  ]}
                >
                  <MarkdownText
                    content={item.text}
                    style={isUser ? styles.userBubbleText : styles.botBubbleText}
                    actionStyle={isUser ? styles.userActionText : styles.botActionText}
                  />
                  <View style={[styles.bubbleFooterRow, styles.bubbleFooterRowDefault]}>
                    {item.isFailed && (
                      <View style={styles.failedIndicatorRow}>
                        <View style={styles.failedDot} />
                        <Text style={styles.failedText}>Failed</Text>
                      </View>
                    )}
                    <Text
                      style={[
                        styles.bubbleTimestamp,
                        isUser ? styles.userTimestampText : styles.botTimestampText,
                      ]}
                    >
                      {item.timestamp}
                    </Text>
                  </View>
                </TouchableOpacity>
              </View>
            );
          }}
          ListFooterComponent={
            isTyping ? (
              <View style={[styles.messageBubbleRow, styles.botBubbleRow]}>
                <View style={[styles.bubbleContainer, styles.botBubble, styles.typingBubbleContainer]}>
                  <TypingDotsAnimation color={borderColor} />
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
                <Text style={styles.editingBannerText}>Editing message</Text>
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
            <TextInput
              ref={chatInputRef}
              style={styles.chatTextInput}
              placeholder={editingMessageId ? 'Edit your message...' : `Message ${activePersona.name}...`}
              placeholderTextColor="#6B7280"
              value={inputText}
              onChangeText={setInputText}
              multiline
              maxLength={1000}
            />

            <TouchableOpacity
              style={[
                styles.sendBtn,
                {
                  backgroundColor: inputText.trim() ? borderColor : '#1E1E28',
                },
              ]}
              onPress={() => handleSend()}
              disabled={!inputText.trim() || isTyping}
              activeOpacity={0.8}
            >
              <SendArrowIcon
                size={16}
                color={inputText.trim() ? '#FFFFFF' : '#4B5563'}
              />
            </TouchableOpacity>
          </View>
        </View>

        {/* Instagram-style Message Action Modal */}
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
            <View style={styles.igOverlayContent} onStartShouldSetResponder={() => true}>
              {/* Spotlighted bubble preview */}
              {actionMenuMessage && (
                <View style={styles.igPreviewBubbleWrapper}>
                  <View
                    style={[
                      styles.bubbleContainer,
                      styles.userBubble,
                      { backgroundColor: borderColor },
                      styles.igElevatedBubble,
                    ]}
                  >
                    <MarkdownText
                      content={actionMenuMessage.text}
                      style={styles.userBubbleText}
                      actionStyle={styles.userActionText}
                    />
                    <View style={[styles.bubbleFooterRow, styles.bubbleFooterRowDefault]}>
                      {actionMenuMessage.isFailed && (
                        <View style={styles.failedIndicatorRow}>
                          <View style={styles.failedDot} />
                          <Text style={styles.failedText}>Failed</Text>
                        </View>
                      )}
                      <Text style={[styles.bubbleTimestamp, styles.userTimestampText]}>
                        {actionMenuMessage.timestamp}
                      </Text>
                    </View>
                  </View>
                </View>
              )}

              {/* Floating Instagram Action Menu Card */}
              {actionMenuMessage && (
                <View style={styles.igActionCard}>
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
                </View>
              )}
            </View>
          </TouchableOpacity>
        </Modal>

        {/* Fullscreen DP / Avatar Viewer - Netflix Paused Photo Preview */}
        {isPreviewImageOpen && (
          <ImagePreviewModal
            visible={isPreviewImageOpen}
            imageUrl={activePersona.image_url}
            name={activePersona.name}
            tagline={activePersona.tagline}
            borderColor={borderColor}
            onClose={() => setIsPreviewImageOpen(false)}
          />
        )}
      </SafeAreaView>

      {/* Persona Details & Mind Profile Modal */}
      <PersonaDetailModal
        visible={isDetailModalOpen}
        persona={activePersona}
        onClose={() => setIsDetailModalOpen(false)}
        onInitiateChat={() => setIsDetailModalOpen(false)}
      />
    </Modal>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#09090D',
  },
  topHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#161622',
    backgroundColor: '#09090D',
  },
  backBtn: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: '#14141E',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: '#222232',
  },
  headerProfileCol: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    flex: 1,
    marginLeft: 10,
  },
  headerSquircle: {
    width: 40,
    height: 40,
    borderRadius: 14,
    borderWidth: 1.8,
    overflow: 'hidden',
    backgroundColor: '#12121A',
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
    backgroundColor: '#1E1E2A',
    borderColor: '#323244',
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
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    marginTop: 2,
  },
  onlineDot: {
    width: 6.5,
    height: 6.5,
    borderRadius: 3.5,
    backgroundColor: '#10B981',
  },
  headerStatusText: {
    fontSize: 11,
    color: '#9CA3AF',
    fontWeight: '500',
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
    backgroundColor: '#14141E',
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
    backgroundColor: '#151522',
    borderWidth: 1,
    borderColor: '#262638',
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
    borderBottomRightRadius: 4,
  },
  botBubble: {
    backgroundColor: '#151520',
    borderWidth: 1,
    borderColor: '#242436',
    borderBottomLeftRadius: 4,
  },
  userBubbleText: {
    fontSize: 15,
    color: '#FFFFFF',
    lineHeight: 22,
  },
  botBubbleText: {
    fontSize: 15,
    color: '#F3F4F6',
    lineHeight: 22,
  },
  userActionText: {
    fontStyle: 'italic',
    color: '#FFE4E6',
  },
  botActionText: {
    fontStyle: 'italic',
    color: '#94A3B8',
  },
  bubbleFooterRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 6,
  },
  bubbleFooterRowDefault: {
    justifyContent: 'flex-end',
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
  igOverlayBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.72)',
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 20,
  },
  igOverlayContent: {
    width: '100%',
    alignItems: 'flex-end',
  },
  igPreviewBubbleWrapper: {
    maxWidth: '85%',
    marginBottom: 10,
  },
  igElevatedBubble: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.5,
    shadowRadius: 10,
    elevation: 10,
  },
  igActionCard: {
    minWidth: 170,
    backgroundColor: '#1E1E26',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#2F2F3D',
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
  igActionText: {
    fontSize: 14.5,
    fontWeight: '600',
    color: '#FFFFFF',
    letterSpacing: 0.2,
  },
  igActionDivider: {
    height: 1,
    backgroundColor: '#292936',
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
    backgroundColor: '#12121A',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#242434',
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
    color: '#64748B',
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
    backgroundColor: '#09090D',
    borderTopWidth: 1,
    borderTopColor: '#161622',
  },
  inputCapsule: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#14141E',
    borderRadius: 25,
    borderWidth: 1,
    borderColor: '#262638',
    paddingLeft: 16,
    paddingRight: 6,
    paddingVertical: 4,
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
