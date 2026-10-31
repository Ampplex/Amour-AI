import React, { useState, useRef } from 'react';
import {
  StyleSheet,
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
  Image,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import * as ImagePicker from 'expo-image-picker';
import AmourLogoVector from '../../components/AmourLogoVector';
import MarkdownText from '../../components/MarkdownText';
import {
  PhotoUploadIcon,
  SparklesIcon,
  CheckmarkCircleIcon,
  ArrowBackIcon,
  SilhouetteUserIcon,
  ShieldLockIcon,
  GlobeIcon,
} from '../../components/CreateBotIcons';
import { API_CONFIG } from '../../constants/authConfig';
import { savePersonaToRoster } from '../../services/personaService';
import { showAlert } from '../../context/AlertContext';
import { useAuth } from '../../context/AuthContext';

// Border color palette options for Avatar Portrait
const BORDER_COLORS = [
  { label: 'Crimson', color: '#F43F5E' },
  { label: 'Violet', color: '#8B5CF6' },
  { label: 'Emerald', color: '#10B981' },
  { label: 'Amber', color: '#F59E0B' },
  { label: 'Sapphire', color: '#3B82F6' },
];

const MEMORY_TAGS = [
  { label: 'Relationship', template: '\nRelationship: ' },
  { label: 'Romantic Dynamic', template: '\nDynamic: ' },
  { label: 'Personality & Quirks', template: '\nPersonality & Quirks: ' },
  { label: 'Love Language', template: '\nLove Language: ' },
  { label: 'Shared Lore', template: '\nShared Lore: ' },
  { label: 'Texting Style', template: '\nTexting Style: ' },
];

export default function CreateBotScreen() {
  const { user } = useAuth();
  // Stage 0: Amour Studio Portal, Stage 1: Persona, Stage 2: Mind & Voice, Stage 3: Launch
  const [stage, setStage] = useState<number>(0);

  // Form State
  const [imageUri, setImageUri] = useState<string | null>(null);
  const [borderColor, setBorderColor] = useState<string>('#F43F5E');
  const [isUploadingPhoto, setIsUploadingPhoto] = useState<boolean>(false);
  const [botName, setBotName] = useState<string>('');
  const [age, setAge] = useState<string>('21');
  const [tagline, setTagline] = useState<string>('');
  const [accessTier, setAccessTier] = useState<'private' | 'public'>('private');
  const [greeting, setGreeting] = useState<string>('');
  const [memoryProfile, setMemoryProfile] = useState<string>('');

  // AI Generation Loading States (Llama 3.1 8B via Bedrock)
  const [isAiGeneratingName, setIsAiGeneratingName] = useState<boolean>(false);
  const [isAiGeneratingGreeting, setIsAiGeneratingGreeting] = useState<boolean>(false);
  const [isAiGeneratingMemory, setIsAiGeneratingMemory] = useState<boolean>(false);
  const [isDeploying, setIsDeploying] = useState<boolean>(false);

  // Input refs
  const nameInputRef = useRef<any>(null);
  const taglineInputRef = useRef<any>(null);
  const greetingInputRef = useRef<any>(null);
  const memoryInputRef = useRef<any>(null);

  // Photo Picker
  const handlePickPhoto = async () => {
    try {
      const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (!permission.granted) {
        showAlert('Permission Needed', 'Please allow photo library access to choose an avatar image.', [{ text: 'OK', style: 'primary' }], 'warning');
        return;
      }

      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ['images'],
        allowsEditing: true,
        aspect: [1, 1],
        quality: 0.8,
        base64: true,
      });

      if (!result.canceled && result.assets && result.assets.length > 0) {
        const asset = result.assets[0];
        setImageUri(asset.uri);

        // Upload in background to backend
        setIsUploadingPhoto(true);
        if (asset.base64) {
          await fetch(`${API_CONFIG.baseUrl}/memory/upload-image/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              image_base64: asset.base64,
              filename: asset.fileName || 'avatar.jpg',
            }),
          });
        }
      }
    } catch (err) {
      console.log('[ImageUpload] Error:', err);
    } finally {
      setIsUploadingPhoto(false);
    }
  };

  // AI Persona Spark
  const handleSparkPersona = async () => {
    setIsAiGeneratingName(true);
    try {
      const res = await fetch(`${API_CONFIG.baseUrl}/memory/generate-persona/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ field: 'name' }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.name) setBotName(data.name);
        if (data.age) setAge(String(data.age));
        if (data.tagline) setTagline(data.tagline);
        return;
      }
      showAlert('Generation Notice', 'Could not generate persona right now. Please try again.', [{ text: 'OK', style: 'primary' }], 'warning');
    } catch (e) {
      console.log('[AI Spark] error:', e);
      showAlert('Connection Issue', 'Could not reach server to generate persona.', [{ text: 'OK', style: 'primary' }], 'warning');
    } finally {
      setIsAiGeneratingName(false);
    }
  };

  // AI Voice Spark
  const handleSparkGreeting = async () => {
    setIsAiGeneratingGreeting(true);
    try {
      const res = await fetch(`${API_CONFIG.baseUrl}/memory/generate-persona/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ field: 'greeting', name: botName, tagline }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.greeting) {
          setGreeting(data.greeting);
          return;
        }
      }
      showAlert('Generation Notice', 'Could not generate greeting opener right now. Please try again.', [{ text: 'OK', style: 'primary' }], 'warning');
    } catch (e) {
      console.log('[AI Greeting] error:', e);
      showAlert('Connection Issue', 'Could not reach server to generate greeting opener.', [{ text: 'OK', style: 'primary' }], 'warning');
    } finally {
      setIsAiGeneratingGreeting(false);
    }
  };

  // AI Memory Spark
  const handleSparkMemory = async () => {
    setIsAiGeneratingMemory(true);
    try {
      const res = await fetch(`${API_CONFIG.baseUrl}/memory/generate-persona/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ field: 'memory', name: botName, tagline }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.memory) {
          setMemoryProfile(data.memory);
          return;
        }
      }
      showAlert('Generation Notice', 'Could not generate memory profile right now. Please try again.', [{ text: 'OK', style: 'primary' }], 'warning');
    } catch (e) {
      console.log('[AI Memory] error:', e);
      showAlert('Connection Issue', 'Could not reach server to generate memory profile.', [{ text: 'OK', style: 'primary' }], 'warning');
    } finally {
      setIsAiGeneratingMemory(false);
    }
  };

  // Append Tag
  const handleAddTag = (template: string) => {
    setMemoryProfile((prev) => (prev ? `${prev.trim()}${template}` : template.trimStart()));
    setTimeout(() => {
      memoryInputRef.current?.focus();
    }, 100);
  };

  const handleCancelStudio = () => {
    showAlert(
      'Exit Avatar Studio',
      'Any unsaved details will be discarded. Exit to home?',
      [
        { text: 'Keep Designing', style: 'cancel' },
        {
          text: 'Exit',
          style: 'destructive',
          onPress: () => {
            setStage(0);
            setBotName('');
            setAge('21');
            setTagline('');
            setImageUri(null);
            setGreeting('');
            setMemoryProfile('');
            router.replace('/(tabs)');
          },
        },
      ],
      'danger'
    );
  };

  const handleLaunchAvatar = async () => {
    if (!botName.trim()) {
      showAlert('Name Required', 'Please provide a name for your avatar.', [{ text: 'OK', style: 'primary' }], 'warning');
      return;
    }

    setIsDeploying(true);
    try {
      const userHandle = user?.email ? `@${user.email.split('@')[0]}` : '@creator';
      await savePersonaToRoster(
        {
          name: botName.trim(),
          age: age ? parseInt(age, 10) : 21,
          tagline: tagline.trim(),
          border_color: borderColor,
          image_url: imageUri || '',
          greeting: greeting.trim(),
          memory_prompt: memoryProfile.trim(),
          visibility: accessTier,
          publisher_name: user?.name || 'Creator',
          publisher_handle: userHandle,
          publisher_avatar: user?.picture || '',
        },
        user?.id
      );
    } catch (e) {
      console.warn('[Amour Studio] Save persona notice:', e);
    } finally {
      setIsDeploying(false);
      showAlert(
        'Avatar Activated',
        `"${botName}" is now live and saved to your roster!`,
        [
          {
            text: 'View Personas',
            style: 'primary',
            onPress: () => {
              setStage(0);
              setBotName('');
              setAge('21');
              setTagline('');
              setImageUri(null);
              setGreeting('');
              setMemoryProfile('');
              router.replace('/(tabs)/personas');
            },
          },
        ],
        'success'
      );
    }
  };

  // Clean Amour Stepper
  const renderAmourStageHeader = (currentStage: number) => (
    <View style={styles.stageHeaderContainer}>
      <View style={styles.stageTopNav}>
        <TouchableOpacity style={styles.closeStageBtn} onPress={handleCancelStudio} activeOpacity={0.7}>
          <Text style={styles.closeStageText}>Close</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.stagePillsRow}>
        <View style={[styles.stagePill, currentStage === 1 && styles.stagePillActive, currentStage > 1 && styles.stagePillCompleted]}>
          <Text style={[styles.stagePillLabel, currentStage === 1 && styles.stagePillLabelActive]}>
            01 Identity
          </Text>
        </View>
        <View style={styles.stageConnector} />
        <View style={[styles.stagePill, currentStage === 2 && styles.stagePillActive, currentStage > 2 && styles.stagePillCompleted]}>
          <Text style={[styles.stagePillLabel, currentStage === 2 && styles.stagePillLabelActive]}>
            02 Voice and Memory
          </Text>
        </View>
        <View style={styles.stageConnector} />
        <View style={[styles.stagePill, currentStage === 3 && styles.stagePillActive]}>
          <Text style={[styles.stagePillLabel, currentStage === 3 && styles.stagePillLabelActive]}>
            03 Review
          </Text>
        </View>
      </View>
    </View>
  );

  // STAGE 0: AMOUR STUDIO PORTAL
  if (stage === 0) {
    return (
      <SafeAreaView style={styles.safeArea} edges={['top']}>
        {/* Top Header */}
        <View style={styles.portalHeader}>
          <TouchableOpacity
            style={styles.portalBackBtn}
            onPress={() => router.replace('/(tabs)')}
            activeOpacity={0.7}
          >
            <ArrowBackIcon color="#FFFFFF" size={24} />
          </TouchableOpacity>
          <Text style={styles.portalBrandTitle}>AMOUR STUDIO</Text>
          <View style={{ width: 32 }} />
        </View>

        {/* Center Showcase */}
        <View style={styles.portalCenter}>
          <View style={styles.portalEmblemGlowRing}>
            <View style={styles.portalEmblemCore}>
              <AmourLogoVector size={105} showText={false} animated={false} />
            </View>
          </View>

          <Text style={styles.portalHeroTitle}>Create a Companion</Text>
          <Text style={styles.portalHeroSubtitle}>
            Bring a unique companion to life with their own personality, style, and greeting.
          </Text>
        </View>

        {/* Bottom CTA */}
        <View style={styles.portalBottomBar}>
          <TouchableOpacity
            style={styles.amourPrimaryCta}
            onPress={() => setStage(1)}
            activeOpacity={0.85}
          >
            <Text style={styles.amourPrimaryCtaText}>Enter Studio</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  // STAGE 1: PERSONA & IDENTITY
  if (stage === 1) {
    const isStepReady = botName.trim().length > 0;

    return (
      <SafeAreaView style={styles.safeArea} edges={['top']}>
        <KeyboardAvoidingView
          style={styles.keyboardContainer}
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        >
          {renderAmourStageHeader(1)}

          <ScrollView
            contentContainerStyle={styles.studioScroll}
            showsVerticalScrollIndicator={false}
            keyboardShouldPersistTaps="handled"
          >
            {/* Stage Title */}
            <View style={styles.stageTitleBlock}>
              <Text style={styles.stageTitleText}>Avatar Identity</Text>
              <Text style={styles.stageSubtitleText}>
                Choose a photo, name, and headline for your companion.
              </Text>
            </View>

            {/* Avatar Visuals Card with Dynamic Border Color Interface */}
            <View style={styles.studioCard}>
              <View style={styles.cardHeaderRow}>
                <Text style={styles.cardHeaderLabel}>AVATAR PORTRAIT</Text>
                <TouchableOpacity
                  style={styles.cardHeaderAction}
                  onPress={handlePickPhoto}
                  disabled={isUploadingPhoto}
                  activeOpacity={0.7}
                >
                  <PhotoUploadIcon color="#F43F5E" size={14} />
                  <Text style={styles.cardHeaderActionText}>
                    {imageUri ? 'Change Photo' : 'Upload Photo'}
                  </Text>
                </TouchableOpacity>
              </View>

              <View style={styles.portraitShowcaseRow}>
                {/* Squircle with dynamic border color */}
                <TouchableOpacity
                  style={[styles.portraitSquircle, { borderColor }]}
                  onPress={handlePickPhoto}
                  activeOpacity={0.8}
                >
                  {imageUri ? (
                    <Image source={{ uri: imageUri }} style={styles.portraitImg} />
                  ) : (
                    <View style={styles.portraitFallback}>
                      <SilhouetteUserIcon color="#FFFFFF" size={48} />
                    </View>
                  )}
                  <View style={styles.portraitOverlayTag}>
                    <PhotoUploadIcon color="#FFFFFF" size={13} />
                  </View>
                </TouchableOpacity>

                {/* Border Color Interface */}
                <View style={styles.borderColorCol}>
                  <Text style={styles.borderColorTitle}>Border Color</Text>
                  <Text style={styles.borderColorSub}>Choose portrait border</Text>
                  <View style={styles.borderColorDotsRow}>
                    {BORDER_COLORS.map((item) => (
                      <TouchableOpacity
                        key={item.label}
                        style={[
                          styles.borderColorDot,
                          { backgroundColor: item.color },
                          borderColor === item.color && styles.borderColorDotActive,
                        ]}
                        onPress={() => setBorderColor(item.color)}
                        activeOpacity={0.7}
                      />
                    ))}
                  </View>
                </View>
              </View>
            </View>

            {/* Name & Archetype Card */}
            <View style={styles.studioCard}>
              <View style={styles.cardHeaderRow}>
                <Text style={styles.cardHeaderLabel}>AVATAR NAME AND ARCHETYPE</Text>
                <TouchableOpacity
                  style={styles.sparkAiBtn}
                  onPress={handleSparkPersona}
                  disabled={isAiGeneratingName}
                  activeOpacity={0.7}
                >
                  {isAiGeneratingName ? (
                    <ActivityIndicator size="small" color="#F43F5E" />
                  ) : (
                    <SparklesIcon color="#F43F5E" size={14} />
                  )}
                  <Text style={styles.sparkAiBtnText}>Spark with AI</Text>
                </TouchableOpacity>
              </View>

              <View style={styles.inputGroup}>
                <Text style={styles.inputFieldTitle}>Name</Text>
                <TextInput
                  ref={nameInputRef}
                  style={styles.studioTextInput}
                  placeholder="e.g. Lila, Liam, Chloe, Alexander, Damian"
                  placeholderTextColor="#52525B"
                  value={botName}
                  onChangeText={setBotName}
                />
              </View>

              <View style={styles.inputGroup}>
                <Text style={styles.inputFieldTitle}>Age</Text>
                <TextInput
                  style={styles.studioTextInput}
                  placeholder="e.g. 21"
                  placeholderTextColor="#52525B"
                  keyboardType="number-pad"
                  value={age}
                  onChangeText={(val) => setAge(val.replace(/[^0-9]/g, ''))}
                  maxLength={3}
                />
              </View>

              <View style={styles.inputGroup}>
                <Text style={styles.inputFieldTitle}>Relationship Tagline</Text>
                <TextInput
                  ref={taglineInputRef}
                  style={styles.studioTextInput}
                  placeholder="e.g. Sweet girlfriend who can't stop texting you"
                  placeholderTextColor="#52525B"
                  value={tagline}
                  onChangeText={setTagline}
                />
              </View>
            </View>

            {/* Visibility Section */}
            <View style={styles.studioCard}>
              <Text style={styles.cardHeaderLabel}>VISIBILITY</Text>

              <View style={styles.vaultTiersRow}>
                <TouchableOpacity
                  style={[
                    styles.vaultTierCard,
                    accessTier === 'private' && styles.vaultTierCardActive,
                  ]}
                  onPress={() => setAccessTier('private')}
                  activeOpacity={0.8}
                >
                  <View style={styles.vaultTierIconRow}>
                    <ShieldLockIcon
                      color={accessTier === 'private' ? '#F43F5E' : '#71717A'}
                      size={20}
                    />
                    {accessTier === 'private' && (
                      <CheckmarkCircleIcon color="#F43F5E" size={18} />
                    )}
                  </View>
                  <Text style={styles.vaultTierTitle}>Private Room</Text>
                  <Text style={styles.vaultTierDesc}>
                    Exclusive to you. Only you can interact with this avatar.
                  </Text>
                </TouchableOpacity>

                <TouchableOpacity
                  style={[
                    styles.vaultTierCard,
                    accessTier === 'public' && styles.vaultTierCardActive,
                  ]}
                  onPress={() => setAccessTier('public')}
                  activeOpacity={0.8}
                >
                  <View style={styles.vaultTierIconRow}>
                    <GlobeIcon
                      color={accessTier === 'public' ? '#F43F5E' : '#71717A'}
                      size={20}
                    />
                    {accessTier === 'public' && (
                      <CheckmarkCircleIcon color="#F43F5E" size={18} />
                    )}
                  </View>
                  <Text style={styles.vaultTierTitle}>Community Lounge</Text>
                  <Text style={styles.vaultTierDesc}>
                    Listed for discovery. Other users can interact with your avatar.
                  </Text>
                </TouchableOpacity>
              </View>
            </View>
          </ScrollView>

          {/* Bottom Navigation CTA */}
          <View style={styles.stageBottomBar}>
            <TouchableOpacity
              style={[styles.amourPrimaryCta, !isStepReady && styles.amourCtaDisabled]}
              onPress={() => setStage(2)}
              disabled={!isStepReady}
              activeOpacity={0.85}
            >
              <Text style={[styles.amourPrimaryCtaText, !isStepReady && styles.amourCtaTextDisabled]}>
                Proceed to Voice and Memory
              </Text>
            </TouchableOpacity>
          </View>
        </KeyboardAvoidingView>
      </SafeAreaView>
    );
  }

  // STAGE 2: MIND & VOICE
  if (stage === 2) {
    return (
      <SafeAreaView style={styles.safeArea} edges={['top']}>
        <KeyboardAvoidingView
          style={styles.keyboardContainer}
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        >
          {renderAmourStageHeader(2)}

          <ScrollView
            contentContainerStyle={styles.studioScroll}
            showsVerticalScrollIndicator={false}
            keyboardShouldPersistTaps="handled"
          >
            {/* Stage Title */}
            <View style={styles.stageTitleBlock}>
              <Text style={styles.stageTitleText}>Voice and Memory</Text>
              <Text style={styles.stageSubtitleText}>
                Define conversational greetings and enduring memory context.
              </Text>
            </View>

            {/* Avatar Header Preview Banner with Chosen Border Color */}
            <View style={styles.avatarMiniBanner}>
              <View style={[styles.avatarMiniSquircle, { borderColor, borderWidth: 2 }]}>
                {imageUri ? (
                  <Image source={{ uri: imageUri }} style={styles.avatarMiniImg} />
                ) : (
                  <SilhouetteUserIcon color="#FFFFFF" size={24} />
                )}
              </View>
              <View style={styles.avatarMiniInfo}>
                <Text style={styles.avatarMiniName}>{botName || 'Avatar'}{age ? `, ${age}` : ''}</Text>
                {tagline ? <Text style={styles.avatarMiniTagline}>{tagline}</Text> : null}
              </View>
            </View>

            {/* First Message Card */}
            <View style={styles.studioCard}>
              <View style={styles.cardHeaderRow}>
                <Text style={styles.cardHeaderLabel}>OPENING GREETING</Text>
                <TouchableOpacity
                  style={styles.sparkAiBtn}
                  onPress={handleSparkGreeting}
                  disabled={isAiGeneratingGreeting}
                  activeOpacity={0.7}
                >
                  {isAiGeneratingGreeting ? (
                    <ActivityIndicator size="small" color="#F43F5E" />
                  ) : (
                    <SparklesIcon color="#F43F5E" size={14} />
                  )}
                  <Text style={styles.sparkAiBtnText}>Inspire Opener</Text>
                </TouchableOpacity>
              </View>

              <TextInput
                ref={greetingInputRef}
                style={styles.multilineStudioInput}
                placeholder="Opening scene or first message (e.g. *leans in with a soft smile* Hey, I missed you today...)"
                placeholderTextColor="#52525B"
                value={greeting}
                onChangeText={setGreeting}
                multiline
                numberOfLines={3}
                textAlignVertical="top"
              />

              {/* Live Formatted Chat Bubble Preview */}
              {greeting ? (
                <View style={styles.chatBubblePreviewContainer}>
                  <Text style={styles.chatBubblePreviewHeader}>LIVE CHAT PREVIEW</Text>
                  <View style={styles.amourChatBubble}>
                    <MarkdownText content={greeting} style={styles.chatBubbleText} />
                  </View>
                </View>
              ) : null}
            </View>

            {/* Memory Profile Card */}
            <View style={styles.studioCard}>
              <View style={styles.cardHeaderRow}>
                <Text style={styles.cardHeaderLabel}>PERSONALITY AND MEMORY</Text>
                <TouchableOpacity
                  style={styles.sparkAiBtn}
                  onPress={handleSparkMemory}
                  disabled={isAiGeneratingMemory}
                  activeOpacity={0.7}
                >
                  {isAiGeneratingMemory ? (
                    <ActivityIndicator size="small" color="#F43F5E" />
                  ) : (
                    <SparklesIcon color="#F43F5E" size={14} />
                  )}
                  <Text style={styles.sparkAiBtnText}>Inspire Memory</Text>
                </TouchableOpacity>
              </View>

              <TextInput
                ref={memoryInputRef}
                style={styles.memoryStudioInput}
                placeholder="Dynamic, backstory, love language, and habits (leave blank or inspire with AI)..."
                placeholderTextColor="#52525B"
                value={memoryProfile}
                onChangeText={setMemoryProfile}
                multiline
                numberOfLines={4}
                textAlignVertical="top"
              />

              {/* Clean Suggested Tags (No Emojis) */}
              <View style={styles.matrixTagsSection}>
                <Text style={styles.matrixTagsHeader}>SUGGESTED ATTRIBUTES</Text>
                <View style={styles.matrixTagsWrap}>
                  {MEMORY_TAGS.map((tag) => (
                    <TouchableOpacity
                      key={tag.label}
                      style={styles.matrixTagPill}
                      onPress={() => handleAddTag(tag.template)}
                      activeOpacity={0.7}
                    >
                      <Text style={styles.matrixTagPillText}>{tag.label}</Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </View>
            </View>
          </ScrollView>

          {/* Bottom Navigation CTA */}
          <View style={styles.stageBottomCol}>
            <TouchableOpacity
              style={styles.amourPrimaryCta}
              onPress={() => setStage(3)}
              activeOpacity={0.85}
            >
              <Text style={styles.amourPrimaryCtaText}>Review and Activate</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.stageBackLink}
              onPress={() => setStage(1)}
              activeOpacity={0.7}
            >
              <Text style={styles.stageBackLinkText}>Back to Persona</Text>
            </TouchableOpacity>
          </View>
        </KeyboardAvoidingView>
      </SafeAreaView>
    );
  }

  // STAGE 3: LAUNCH & ACTIVATION
  return (
    <SafeAreaView style={styles.safeArea} edges={['top']}>
      {renderAmourStageHeader(3)}

      <ScrollView contentContainerStyle={styles.studioScroll} showsVerticalScrollIndicator={false}>
        {/* Stage Title */}
        <View style={styles.stageTitleBlock}>
          <Text style={styles.stageTitleText}>Avatar Profile</Text>
          <Text style={styles.stageSubtitleText}>
            Review your companion before saving.
          </Text>
        </View>

        {/* Amour Passport Card */}
        <View style={styles.passportCard}>
          <View style={styles.passportTopRow}>
            {/* Avatar Squircle with Selected Border Color */}
            <View style={[styles.passportSquircle, { borderColor, borderWidth: 2 }]}>
              {imageUri ? (
                <Image source={{ uri: imageUri }} style={styles.passportImg} />
              ) : (
                <View style={styles.passportFallback}>
                  <SilhouetteUserIcon color="#FFFFFF" size={42} />
                </View>
              )}
            </View>

            <View style={styles.passportInfoCol}>
              <Text style={styles.passportAvatarName}>{botName || 'Avatar'}{age ? `, ${age}` : ''}</Text>
              {tagline ? <Text style={styles.passportAvatarTagline}>{tagline}</Text> : null}
              <View style={styles.passportPillRow}>
                <View style={styles.passportAccessPill}>
                  <Text style={styles.passportAccessPillText}>
                    {accessTier === 'private' ? 'Private Room' : 'Community Lounge'}
                  </Text>
                </View>
              </View>
            </View>
          </View>

          {/* Greeting Section */}
          <View style={styles.passportSection}>
            <Text style={styles.passportSectionLabel}>FIRST MESSAGE</Text>
            <View style={styles.passportBubbleBox}>
              <MarkdownText
                content={greeting || "*smiles gently* Ready when you are."}
                style={styles.passportBubbleText}
              />
            </View>
          </View>

          {/* Memory Section */}
          <View style={styles.passportSection}>
            <Text style={styles.passportSectionLabel}>PERSONALITY AND STORY</Text>
            <View style={styles.passportMemoryBox}>
              <MarkdownText
                content={memoryProfile || "A thoughtful companion ready to chat."}
                style={styles.passportMemoryText}
              />
            </View>
          </View>
        </View>
      </ScrollView>

      {/* Bottom Launch CTAs */}
      <View style={styles.stageBottomCol}>
        <TouchableOpacity
          style={[styles.amourPrimaryCta, isDeploying && styles.amourCtaDisabled]}
          onPress={handleLaunchAvatar}
          disabled={isDeploying}
          activeOpacity={0.85}
        >
          {isDeploying ? (
            <ActivityIndicator size="small" color="#FFFFFF" />
          ) : (
            <Text style={styles.amourPrimaryCtaText}>Save Persona</Text>
          )}
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.stageBackLink}
          onPress={() => setStage(2)}
          activeOpacity={0.7}
        >
          <Text style={styles.stageBackLinkText}>Edit Voice and Memory</Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#09090D',
  },
  keyboardContainer: {
    flex: 1,
  },

  // PORTAL (STAGE 0)
  portalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingVertical: 12,
  },
  portalBackBtn: {
    padding: 6,
  },
  portalBrandTitle: {
    color: '#FFFFFF',
    fontFamily: 'ChangaOne-Regular',
    fontSize: 20,
    letterSpacing: 1.2,
  },
  portalCenter: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 28,
    gap: 16,
  },
  portalEmblemGlowRing: {
    width: 130,
    height: 130,
    borderRadius: 65,
    backgroundColor: 'rgba(244, 63, 94, 0.12)',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: 'rgba(244, 63, 94, 0.3)',
    marginBottom: 6,
  },
  portalEmblemCore: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  portalHeroTitle: {
    color: '#FFFFFF',
    fontFamily: 'ChangaOne-Regular',
    fontSize: 34,
    textAlign: 'center',
    letterSpacing: 0.5,
  },
  portalHeroSubtitle: {
    color: '#A1A1AA',
    fontSize: 15,
    lineHeight: 23,
    textAlign: 'center',
    maxWidth: 320,
  },
  portalBottomBar: {
    paddingHorizontal: 20,
    paddingBottom: Platform.OS === 'ios' ? 16 : 22,
    paddingTop: 10,
  },

  // STAGE HEADER & CAPSULES
  stageHeaderContainer: {
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 12,
    gap: 12,
  },
  stageTopNav: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  closeStageBtn: {
    backgroundColor: '#171720',
    borderWidth: 1,
    borderColor: '#242432',
    borderRadius: 16,
    paddingHorizontal: 14,
    paddingVertical: 6,
  },
  closeStageText: {
    color: '#A1A1AA',
    fontSize: 13,
    fontWeight: '500',
  },
  stagePillsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  stagePill: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 7,
    borderRadius: 12,
    backgroundColor: '#14141C',
    borderWidth: 1,
    borderColor: '#20202B',
  },
  stagePillActive: {
    backgroundColor: '#26131A',
    borderColor: '#F43F5E',
  },
  stagePillCompleted: {
    backgroundColor: '#1E1B26',
    borderColor: '#4A3D63',
  },
  stagePillLabel: {
    color: '#71717A',
    fontFamily: 'ChangaOne-Regular',
    fontSize: 12,
  },
  stagePillLabelActive: {
    color: '#F43F5E',
  },
  stageConnector: {
    width: 6,
    height: 1,
    backgroundColor: '#272736',
  },

  // STAGE BODY
  studioScroll: {
    paddingHorizontal: 16,
    paddingBottom: 24,
    gap: 16,
  },
  stageTitleBlock: {
    gap: 4,
    marginTop: 4,
  },
  stageTitleText: {
    color: '#FFFFFF',
    fontFamily: 'ChangaOne-Regular',
    fontSize: 26,
    letterSpacing: 0.3,
  },
  stageSubtitleText: {
    color: '#8A8A99',
    fontSize: 13,
    lineHeight: 19,
  },

  // STUDIO CARD
  studioCard: {
    backgroundColor: '#121218',
    borderWidth: 1,
    borderColor: '#20202B',
    borderRadius: 18,
    padding: 16,
    gap: 14,
  },
  cardHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  cardHeaderLabel: {
    color: '#A1A1AA',
    fontFamily: 'ChangaOne-Regular',
    fontSize: 12,
    letterSpacing: 0.8,
  },
  cardHeaderAction: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
  },
  cardHeaderActionText: {
    color: '#F43F5E',
    fontSize: 13,
    fontWeight: '600',
  },

  // PORTRAIT & BORDER COLOR INTERFACE
  portraitShowcaseRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 18,
  },
  portraitSquircle: {
    width: 88,
    height: 88,
    borderRadius: 22,
    backgroundColor: '#1E1E28',
    borderWidth: 2,
    overflow: 'hidden',
    position: 'relative',
    alignItems: 'center',
    justifyContent: 'center',
  },
  portraitImg: {
    width: '100%',
    height: '100%',
  },
  portraitFallback: {
    width: '100%',
    height: '100%',
    backgroundColor: '#F43F5E',
    alignItems: 'center',
    justifyContent: 'center',
  },
  portraitOverlayTag: {
    position: 'absolute',
    bottom: 4,
    right: 4,
    backgroundColor: 'rgba(0,0,0,0.7)',
    borderRadius: 10,
    padding: 4,
  },
  borderColorCol: {
    flex: 1,
    gap: 4,
  },
  borderColorTitle: {
    color: '#FFFFFF',
    fontFamily: 'ChangaOne-Regular',
    fontSize: 15,
  },
  borderColorSub: {
    color: '#71717A',
    fontSize: 12,
  },
  borderColorDotsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 6,
  },
  borderColorDot: {
    width: 22,
    height: 22,
    borderRadius: 11,
  },
  borderColorDotActive: {
    borderWidth: 2,
    borderColor: '#FFFFFF',
    transform: [{ scale: 1.15 }],
  },

  // INPUT GROUPS
  inputGroup: {
    gap: 6,
  },
  inputFieldTitle: {
    color: '#D4D4D8',
    fontSize: 13,
    fontWeight: '500',
  },
  studioTextInput: {
    backgroundColor: '#0A0A0E',
    borderWidth: 1,
    borderColor: '#242432',
    borderRadius: 14,
    paddingHorizontal: 14,
    paddingVertical: 12,
    color: '#FFFFFF',
    fontSize: 15,
  },
  sparkAiBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    backgroundColor: 'rgba(244, 63, 94, 0.1)',
    borderWidth: 1,
    borderColor: 'rgba(244, 63, 94, 0.3)',
    borderRadius: 14,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  sparkAiBtnText: {
    color: '#F43F5E',
    fontFamily: 'ChangaOne-Regular',
    fontSize: 12,
  },

  // PRIVACY TIERS
  vaultTiersRow: {
    gap: 10,
  },
  vaultTierCard: {
    backgroundColor: '#0A0A0E',
    borderWidth: 1,
    borderColor: '#22222E',
    borderRadius: 16,
    padding: 14,
    gap: 4,
  },
  vaultTierCardActive: {
    borderColor: '#F43F5E',
    backgroundColor: '#170E12',
  },
  vaultTierIconRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 2,
  },
  vaultTierTitle: {
    color: '#FFFFFF',
    fontFamily: 'ChangaOne-Regular',
    fontSize: 15,
  },
  vaultTierDesc: {
    color: '#8A8A99',
    fontSize: 12,
    lineHeight: 17,
  },

  // STAGE 2 COMPONENTS
  avatarMiniBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    backgroundColor: '#121218',
    borderWidth: 1,
    borderColor: '#20202B',
    borderRadius: 16,
    padding: 12,
  },
  avatarMiniSquircle: {
    width: 44,
    height: 44,
    borderRadius: 12,
    backgroundColor: '#1E1E28',
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
  },
  avatarMiniImg: {
    width: '100%',
    height: '100%',
  },
  avatarMiniInfo: {
    flex: 1,
    gap: 2,
  },
  avatarMiniName: {
    color: '#FFFFFF',
    fontFamily: 'ChangaOne-Regular',
    fontSize: 16,
  },
  avatarMiniTagline: {
    color: '#8A8A99',
    fontSize: 12,
  },
  multilineStudioInput: {
    backgroundColor: '#0A0A0E',
    borderWidth: 1,
    borderColor: '#242432',
    borderRadius: 14,
    paddingHorizontal: 14,
    paddingVertical: 12,
    color: '#FFFFFF',
    fontSize: 14,
    lineHeight: 21,
    minHeight: 74,
  },
  chatBubblePreviewContainer: {
    marginTop: 6,
    gap: 6,
  },
  chatBubblePreviewHeader: {
    color: '#71717A',
    fontFamily: 'ChangaOne-Regular',
    fontSize: 11,
    letterSpacing: 0.6,
  },
  amourChatBubble: {
    backgroundColor: '#1B1420',
    borderWidth: 1,
    borderColor: '#37203A',
    borderRadius: 16,
    borderTopLeftRadius: 4,
    padding: 14,
  },
  chatBubbleText: {
    color: '#FFFFFF',
    fontSize: 14,
    lineHeight: 21,
  },
  memoryStudioInput: {
    backgroundColor: '#0A0A0E',
    borderWidth: 1,
    borderColor: '#242432',
    borderRadius: 14,
    paddingHorizontal: 14,
    paddingVertical: 12,
    color: '#FFFFFF',
    fontSize: 14,
    lineHeight: 21,
    minHeight: 90,
  },
  matrixTagsSection: {
    gap: 8,
    marginTop: 4,
  },
  matrixTagsHeader: {
    color: '#71717A',
    fontFamily: 'ChangaOne-Regular',
    fontSize: 11,
    letterSpacing: 0.6,
  },
  matrixTagsWrap: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  matrixTagPill: {
    backgroundColor: '#181822',
    borderWidth: 1,
    borderColor: '#2B2B3C',
    borderRadius: 14,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  matrixTagPillText: {
    color: '#D4D4D8',
    fontSize: 12,
    fontWeight: '500',
  },

  // STAGE 3 PASSPORT
  passportCard: {
    backgroundColor: '#121218',
    borderWidth: 1,
    borderColor: '#282838',
    borderRadius: 22,
    padding: 18,
    gap: 18,
  },
  passportTopRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
  },
  passportSquircle: {
    width: 72,
    height: 72,
    borderRadius: 20,
    backgroundColor: '#1E1E28',
    overflow: 'hidden',
    alignItems: 'center',
    justifyContent: 'center',
  },
  passportImg: {
    width: '100%',
    height: '100%',
  },
  passportFallback: {
    width: '100%',
    height: '100%',
    backgroundColor: '#F43F5E',
    alignItems: 'center',
    justifyContent: 'center',
  },
  passportInfoCol: {
    flex: 1,
    gap: 4,
  },
  passportAvatarName: {
    color: '#FFFFFF',
    fontFamily: 'ChangaOne-Regular',
    fontSize: 22,
  },
  passportAvatarTagline: {
    color: '#A1A1AA',
    fontSize: 13,
  },
  passportPillRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 4,
  },
  passportAccessPill: {
    backgroundColor: '#1F1F2B',
    borderRadius: 10,
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  passportAccessPillText: {
    color: '#A1A1AA',
    fontSize: 11,
    fontWeight: '500',
  },
  passportSection: {
    borderTopWidth: 1,
    borderTopColor: '#20202C',
    paddingTop: 12,
    gap: 8,
  },
  passportSectionLabel: {
    color: '#71717A',
    fontFamily: 'ChangaOne-Regular',
    fontSize: 11,
    letterSpacing: 0.6,
  },
  passportBubbleBox: {
    backgroundColor: '#1A1420',
    borderWidth: 1,
    borderColor: '#36233C',
    borderRadius: 14,
    padding: 12,
  },
  passportBubbleText: {
    color: '#FFFFFF',
    fontSize: 14,
    lineHeight: 21,
  },
  passportMemoryBox: {
    backgroundColor: '#0D0D12',
    borderWidth: 1,
    borderColor: '#20202B',
    borderRadius: 14,
    padding: 12,
  },
  passportMemoryText: {
    color: '#D4D4D8',
    fontSize: 13,
    lineHeight: 20,
  },

  // BOTTOM NAVIGATION
  stageBottomBar: {
    paddingHorizontal: 16,
    paddingBottom: Platform.OS === 'ios' ? 14 : 20,
    paddingTop: 8,
  },
  stageBottomCol: {
    paddingHorizontal: 16,
    paddingBottom: Platform.OS === 'ios' ? 14 : 20,
    paddingTop: 8,
    gap: 10,
    alignItems: 'center',
  },
  amourPrimaryCta: {
    width: '100%',
    backgroundColor: '#F43F5E',
    borderRadius: 28,
    height: 54,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#F43F5E',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 10,
    elevation: 4,
  },
  amourCtaDisabled: {
    backgroundColor: '#261A1F',
    shadowOpacity: 0,
    elevation: 0,
  },
  amourPrimaryCtaText: {
    color: '#FFFFFF',
    fontFamily: 'ChangaOne-Regular',
    fontSize: 17,
    letterSpacing: 0.4,
  },
  amourCtaTextDisabled: {
    color: '#634E57',
  },
  stageBackLink: {
    paddingVertical: 6,
    paddingHorizontal: 16,
  },
  stageBackLinkText: {
    color: '#A1A1AA',
    fontFamily: 'ChangaOne-Regular',
    fontSize: 14,
  },
});
