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
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Svg, { Path, Circle } from 'react-native-svg';
import MarkdownText from './MarkdownText';
import { PersonaItem, updatePersonaMemory } from '../services/personaService';
import { API_CONFIG } from '../constants/authConfig';
import { useAuth } from '../context/AuthContext';

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

interface ChatMessage {
  id: string;
  sender: 'user' | 'bot';
  text: string;
  timestamp: string;
}

interface CompanionChatModalProps {
  visible: boolean;
  persona: PersonaItem | null;
  onClose: () => void;
}

const CANDIDATE_URLS = [
  'http://127.0.0.1:8000/api',
  'http://192.168.1.4:8000/api',
  API_CONFIG.baseUrl,
  'http://10.104.217.217:8000/api',
  'http://192.168.1.2:8000/api',
];

async function tryChatFetch(payload: any, token?: string): Promise<{ reply?: string } | null> {
  for (const base of CANDIDATE_URLS) {
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 12000);
      const res = await fetch(`${base}/memory/chat/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });
      clearTimeout(timer);
      if (res.ok) {
        return await res.json();
      }
    } catch {
      // try next candidate endpoint
    }
  }
  return null;
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
  const [showMemoryModal, setShowMemoryModal] = useState<boolean>(false);
  const [memoryInput, setMemoryInput] = useState<string>('');
  const [greetingInput, setGreetingInput] = useState<string>('');
  const [isSavingMemory, setIsSavingMemory] = useState<boolean>(false);
  const flatListRef = useRef<FlatList>(null);

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

  // Initialize with persona's customized greeting (opening script)
  useEffect(() => {
    if (!visible || !persona) {
      setMessages([]);
      return;
    }

    setActivePersona(persona);
    setMemoryInput(persona.memory_prompt || '');
    setGreetingInput(persona.greeting || '');

    const initialGreeting = persona.greeting || `Hello! I am ${persona.name}. How are you today?`;
    setMessages([
      {
        id: `msg-greeting-${persona.id}`,
        sender: 'bot',
        text: initialGreeting,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    ]);
  }, [visible, persona?.id]);

  const handleSaveMemoryModal = async () => {
    if (!activePersona) return;
    setIsSavingMemory(true);
    try {
      const updated = await updatePersonaMemory(
        activePersona.id,
        {
          greeting: greetingInput.trim(),
          memory_prompt: memoryInput.trim(),
        },
        user?.id
      );
      if (updated) {
        setActivePersona(updated);
        setShowMemoryModal(false);
      }
    } catch (e) {
      console.warn('[CompanionChatModal] Error saving memory:', e);
    } finally {
      setIsSavingMemory(false);
    }
  };

  const handleSend = async () => {
    const text = inputText.trim();
    if (!text || !activePersona || isTyping) return;

    const userMsg: ChatMessage = {
      id: `msg-${Date.now()}`,
      sender: 'user',
      text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputText('');
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

    const payload = {
      message: text,
      persona_id: activePersona.id,
      persona_name: activePersona.name,
      greeting: activePersona.greeting,
      memory_prompt: activePersona.memory_prompt,
      client_time: clientTime,
      client_timezone: clientTimezone,
      user_id: user?.id,
    };

    try {
      const data = await tryChatFetch(payload, user?.token);
      let replyText = data?.reply || '';

      if (!replyText) {
        replyText = "I hear you. Tell me more about what is on your mind.";
      }

      const botReply: ChatMessage = {
        id: `bot-${Date.now()}`,
        sender: 'bot',
        text: replyText,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      setMessages((prev) => [...prev, botReply]);
    } catch (err) {
      const fallbackReply: ChatMessage = {
        id: `bot-fallback-${Date.now()}`,
        sender: 'bot',
        text: "I am listening closely. Tell me more about what you are thinking.",
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, fallbackReply]);
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
            <View style={[styles.headerSquircle, { borderColor }]}>
              {activePersona.image_url ? (
                <Image source={{ uri: activePersona.image_url }} style={styles.headerAvatarImg} />
              ) : (
                <View style={[styles.headerAvatarImg, { backgroundColor: borderColor }]}>
                  <Text style={styles.headerAvatarLetter}>
                    {activePersona.name.charAt(0).toUpperCase()}
                  </Text>
                </View>
              )}
            </View>

            <View style={styles.headerTextCol}>
              <Text style={styles.headerBotName} numberOfLines={1}>{activePersona.name}</Text>
              <View style={styles.statusRow}>
                <View style={styles.onlineDot} />
                <Text style={styles.headerStatusText}>Online · Reeve Memory</Text>
              </View>
            </View>
          </View>

          {/* High-Tech Memory Pill */}
          <TouchableOpacity
            onPress={() => setShowMemoryModal(true)}
            style={styles.memoryPillBtn}
            activeOpacity={0.7}
            hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
            accessibilityLabel="View persona memory"
          >
            <BrainIcon size={13} color="#60A5FA" />
            <Text style={styles.memoryPillText}>Memory</Text>
          </TouchableOpacity>
        </View>

        {/* Messages Flow */}
        <FlatList
          ref={flatListRef}
          data={messages}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.messagesList}
          keyboardShouldPersistTaps="handled"
          onContentSizeChange={() => flatListRef.current?.scrollToEnd({ animated: true })}
          renderItem={({ item }) => {
            const isUser = item.sender === 'user';
            return (
              <View
                style={[
                  styles.messageBubbleRow,
                  isUser ? styles.userBubbleRow : styles.botBubbleRow,
                ]}
              >
                <View
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
                  <Text
                    style={[
                      styles.bubbleTimestamp,
                      isUser ? styles.userTimestampText : styles.botTimestampText,
                    ]}
                  >
                    {item.timestamp}
                  </Text>
                </View>
              </View>
            );
          }}
          ListFooterComponent={
            isTyping ? (
              <View style={styles.typingIndicatorRow}>
                <View style={[styles.typingBubble, { borderColor: '#26263A' }]}>
                  <ActivityIndicator size="small" color={borderColor} />
                  <Text style={styles.typingText}>{activePersona.name} is typing...</Text>
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
          <View style={styles.inputCapsule}>
            <TextInput
              style={styles.chatTextInput}
              placeholder={`Message ${activePersona.name}...`}
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
              onPress={handleSend}
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

        {/* Live In-Chat Memory Tuning Sheet */}
        <Modal
          visible={showMemoryModal}
          animationType="fade"
          transparent={true}
          statusBarTranslucent={true}
          onRequestClose={() => setShowMemoryModal(false)}
        >
          <View style={styles.modalBackdrop}>
            <View style={styles.modalSheetCard}>
              <View style={styles.modalSheetHeader}>
                <View style={styles.modalSheetTitleRow}>
                  <BrainIcon size={16} color="#60A5FA" />
                  <Text style={styles.modalSheetTitle}>Companion Memory (Reeve)</Text>
                </View>
                <TouchableOpacity
                  onPress={() => setShowMemoryModal(false)}
                  style={styles.sheetCloseBtn}
                  hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                >
                  <CloseIcon size={16} color="#FFFFFF" />
                </TouchableOpacity>
              </View>

              <ScrollView style={styles.modalSheetBody} showsVerticalScrollIndicator={false}>
                <Text style={styles.sheetFieldLabel}>FIRST MESSAGE / SCRIPT</Text>
                <TextInput
                  style={styles.sheetInput}
                  value={greetingInput}
                  onChangeText={setGreetingInput}
                  placeholder="First message opening script..."
                  placeholderTextColor="#6B7280"
                  multiline
                  numberOfLines={2}
                />

                <Text style={[styles.sheetFieldLabel, { marginTop: 14 }]}>
                  PERSONALITY & STORY (REEVE GRAPH)
                </Text>
                <TextInput
                  style={[styles.sheetInput, { minHeight: 90 }]}
                  value={memoryInput}
                  onChangeText={setMemoryInput}
                  placeholder="Backstory and memory..."
                  placeholderTextColor="#6B7280"
                  multiline
                  numberOfLines={4}
                />
                <Text style={styles.sheetSubHint}>
                  100% stored in Reeve memory graph. Changes apply on the next turn.
                </Text>

                <View style={styles.sheetActionRow}>
                  <TouchableOpacity
                    style={styles.sheetCancelBtn}
                    onPress={() => setShowMemoryModal(false)}
                  >
                    <Text style={styles.sheetCancelText}>Cancel</Text>
                  </TouchableOpacity>

                  <TouchableOpacity
                    style={[styles.sheetSaveBtn, { backgroundColor: borderColor }]}
                    onPress={handleSaveMemoryModal}
                    disabled={isSavingMemory}
                  >
                    {isSavingMemory ? (
                      <ActivityIndicator size="small" color="#FFFFFF" />
                    ) : (
                      <Text style={styles.sheetSaveText}>Save to Reeve</Text>
                    )}
                  </TouchableOpacity>
                </View>
              </ScrollView>
            </View>
          </View>
        </Modal>
      </SafeAreaView>
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
  memoryPillBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 11,
    paddingVertical: 6,
    borderRadius: 14,
    backgroundColor: 'rgba(59, 130, 246, 0.12)',
    borderWidth: 1,
    borderColor: 'rgba(59, 130, 246, 0.35)',
  },
  memoryPillText: {
    fontSize: 11.5,
    fontWeight: '700',
    color: '#60A5FA',
    letterSpacing: 0.3,
  },
  messagesList: {
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 20,
    gap: 12,
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
  bubbleTimestamp: {
    fontSize: 10,
    alignSelf: 'flex-end',
    marginTop: 4,
  },
  userTimestampText: {
    color: 'rgba(255, 255, 255, 0.75)',
  },
  botTimestampText: {
    color: '#64748B',
  },
  typingIndicatorRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 4,
    marginBottom: 8,
  },
  typingBubble: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: '#151520',
    borderWidth: 1,
    paddingHorizontal: 14,
    paddingVertical: 9,
    borderRadius: 16,
  },
  typingText: {
    fontSize: 12,
    color: '#9CA3AF',
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
  modalBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.75)',
    justifyContent: 'center',
    paddingHorizontal: 20,
  },
  modalSheetCard: {
    backgroundColor: '#101018',
    borderRadius: 20,
    borderWidth: 1,
    borderColor: '#262636',
    padding: 18,
    maxHeight: '80%',
  },
  modalSheetHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 16,
  },
  modalSheetTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  modalSheetTitle: {
    fontFamily: 'ChangaOne-Regular',
    fontSize: 16,
    color: '#FFFFFF',
  },
  sheetCloseBtn: {
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: '#1C1C28',
    alignItems: 'center',
    justifyContent: 'center',
  },
  modalSheetBody: {
    maxHeight: 350,
  },
  sheetFieldLabel: {
    fontSize: 11,
    fontWeight: '700',
    color: '#9CA3AF',
    letterSpacing: 0.5,
    marginBottom: 6,
  },
  sheetInput: {
    backgroundColor: '#161622',
    borderRadius: 12,
    padding: 12,
    color: '#FFFFFF',
    fontSize: 13.5,
    borderWidth: 1,
    borderColor: '#262636',
    textAlignVertical: 'top',
  },
  sheetSubHint: {
    fontSize: 11,
    color: '#60A5FA',
    marginTop: 6,
    fontStyle: 'italic',
  },
  sheetActionRow: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 10,
    marginTop: 18,
    marginBottom: 8,
  },
  sheetCancelBtn: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
    backgroundColor: '#1C1C28',
  },
  sheetCancelText: {
    fontSize: 13,
    color: '#9CA3AF',
  },
  sheetSaveBtn: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 8,
  },
  sheetSaveText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#FFFFFF',
  },
});
