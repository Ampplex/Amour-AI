import React, { useState, useEffect } from 'react';
import {
  StyleSheet,
  View,
  Text,
  TouchableOpacity,
  Image,
  Modal,
  TextInput,
  ActivityIndicator,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Svg, { Path, Circle } from 'react-native-svg';
import * as ImagePicker from 'expo-image-picker';
import { router } from 'expo-router';
import { useAuth } from '../../context/AuthContext';
import { showAlert } from '../../context/AlertContext';

function EditIcon({ size = 16, color = '#FFFFFF' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <Path
        d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

function CameraIcon({ size = 18, color = '#FFFFFF' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <Circle cx="12" cy="13" r="4" stroke={color} strokeWidth="2" />
    </Svg>
  );
}

function CloseIcon({ size = 20, color = '#FFFFFF' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M18 6L6 18M6 6l12 12"
        stroke={color}
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

function CheckIcon({ size = 16, color = '#10B981' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M20 6L9 17l-5-5"
        stroke={color}
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

function UserIcon({ size = 34, color = '#EC4899' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <Circle cx="12" cy="7" r="4" stroke={color} strokeWidth="2" />
    </Svg>
  );
}

export default function ProfileScreen() {
  const { user, logout, updateProfile, uploadProfilePicture, refreshProfile } = useAuth();

  // Edit Profile Modal state
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editName, setEditName] = useState('');
  const [editUsername, setEditUsername] = useState('');
  const [editAvatarUri, setEditAvatarUri] = useState<string | null>(null);
  const [isUploadingPhoto, setIsUploadingPhoto] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [usernameError, setUsernameError] = useState<string | null>(null);

  useEffect(() => {
    if (user?.id) {
      refreshProfile().catch(() => {});
    }
  }, [user?.id]);

  const openEditModal = () => {
    if (!user) return;
    setEditName(user.name || '');
    setEditUsername(user.username || '');
    setEditAvatarUri(user.picture || null);
    setUsernameError(null);
    setIsEditModalOpen(true);
  };

  const closeEditModal = () => {
    setIsEditModalOpen(false);
    setUsernameError(null);
  };

  const handlePickImage = async () => {
    try {
      const permissionResult = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (!permissionResult.granted) {
        showAlert('Permission Denied', 'Please grant photo library access to upload a profile picture.', undefined, 'warning');
        return;
      }

      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ['images'],
        allowsEditing: true,
        aspect: [1, 1],
        quality: 0.8,
        base64: true,
      });

      if (result.canceled || !result.assets || result.assets.length === 0) {
        return;
      }

      const asset = result.assets[0];
      if (!asset.base64) {
        showAlert('Upload Failed', 'Could not read image data. Please select another image.', undefined, 'danger');
        return;
      }

      setIsUploadingPhoto(true);
      const res = await uploadProfilePicture({ base64: asset.base64 });
      setIsUploadingPhoto(false);

      if (res.success && res.url) {
        setEditAvatarUri(res.url);
        showAlert('Photo Updated', 'Your profile picture has been updated.', undefined, 'success');
      } else {
        showAlert('Upload Failed', res.error || 'Failed to upload photo.', undefined, 'danger');
      }
    } catch (err: any) {
      setIsUploadingPhoto(false);
      showAlert('Photo Error', err?.message || 'An error occurred while picking an image.', undefined, 'danger');
    }
  };

  const handleSaveProfile = async () => {
    const cleanUsername = editUsername.toLowerCase().replace(/[^a-z0-9_]/g, '').trim();

    if (cleanUsername.length < 3 || cleanUsername.length > 30) {
      setUsernameError('Username must be 3–30 characters (letters, numbers, underscores).');
      return;
    }

    setIsSaving(true);
    setUsernameError(null);

    const res = await updateProfile({
      username: cleanUsername,
      name: editName.trim() || undefined,
    });

    setIsSaving(false);

    if (res.success) {
      setIsEditModalOpen(false);
      showAlert('Profile Updated', 'Your profile details and persona publisher credits have been saved.', undefined, 'success');
    } else {
      setUsernameError(res.error || 'Failed to update profile.');
    }
  };

  const handleSignOut = () => {
    showAlert(
      'Sign Out',
      'Are you sure you want to sign out from Amour AI?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Sign Out',
          style: 'destructive',
          onPress: async () => {
            await logout();
            router.replace('/login');
          },
        },
      ],
      'danger'
    );
  };

  if (!user) {
    return (
      <SafeAreaView style={styles.safeArea} edges={['top']}>
        <View style={styles.header}>
          <Text style={styles.headerTitle}>Profile</Text>
        </View>

        <View style={styles.guestContainer}>
          <View style={styles.guestIconCircle}>
            <UserIcon size={38} color="#EC4899" />
          </View>
          <Text style={styles.guestTitle}>Welcome to Amour AI</Text>
          <Text style={styles.guestSubtitle}>
            Sign in or create an account to customize your profile, chat with AI companions, and access exclusive personas.
          </Text>

          <TouchableOpacity
            style={styles.guestButton}
            onPress={() => router.push('/login')}
            activeOpacity={0.85}
          >
            <Text style={styles.guestButtonText}>Sign In or Create Account</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  const username = user.username || user.email.split('@')[0] || 'user';

  return (
    <SafeAreaView style={styles.safeArea} edges={['top']}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Profile</Text>
      </View>

      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        {/* User Card */}
        <View style={styles.userCard}>
          <View style={styles.avatarContainer}>
            {user.picture ? (
              <Image source={{ uri: user.picture }} style={styles.avatar} />
            ) : (
              <View style={styles.avatarFallback}>
                <Text style={styles.avatarInitial}>
                  {user.name ? user.name.charAt(0).toUpperCase() : 'U'}
                </Text>
              </View>
            )}
          </View>

          <View style={styles.userTextInfo}>
            <Text style={styles.userName} numberOfLines={1}>{user.name || 'User'}</Text>
            <View style={styles.handleBadge}>
              <Text style={styles.handleText}>@{username}</Text>
            </View>
            <Text style={styles.userEmail} numberOfLines={1}>{user.email}</Text>
          </View>
        </View>

        {/* Edit Profile Action Button */}
        <TouchableOpacity
          style={styles.editProfileButton}
          onPress={openEditModal}
          activeOpacity={0.8}
        >
          <View style={styles.editButtonContent}>
            <View style={styles.editIconCircle}>
              <EditIcon size={16} color="#FFFFFF" />
            </View>
            <View style={styles.editButtonTextContainer}>
              <Text style={styles.editButtonTitle}>Edit Profile</Text>
              <Text style={styles.editButtonSubtitle}>Change name, username & photo</Text>
            </View>
          </View>
          <Text style={styles.editButtonArrow}>›</Text>
        </TouchableOpacity>

        {/* Sign Out */}
        <TouchableOpacity
          style={styles.signOutButton}
          onPress={handleSignOut}
          activeOpacity={0.8}
        >
          <Text style={styles.signOutText}>Sign Out</Text>
        </TouchableOpacity>
      </ScrollView>

      {/* Edit Profile Modal */}
      <Modal
        visible={isEditModalOpen}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={closeEditModal}
      >
        <SafeAreaView style={styles.modalContainer} edges={['top', 'bottom']}>
          {/* Modal Header */}
          <View style={styles.modalHeader}>
            <TouchableOpacity onPress={closeEditModal} style={styles.modalCloseButton} hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}>
              <CloseIcon size={20} color="#FFFFFF" />
            </TouchableOpacity>
            <Text style={styles.modalTitle}>Edit Profile</Text>
            <TouchableOpacity
              onPress={handleSaveProfile}
              style={[styles.modalSaveButton, isSaving && styles.modalSaveButtonDisabled]}
              disabled={isSaving || isUploadingPhoto}
            >
              {isSaving ? (
                <ActivityIndicator size="small" color="#FFFFFF" />
              ) : (
                <Text style={styles.modalSaveText}>Save</Text>
              )}
            </TouchableOpacity>
          </View>

          <KeyboardAvoidingView
            style={styles.modalKeyboardAvoid}
            behavior={Platform.OS === 'ios' ? 'padding' : undefined}
          >
            <ScrollView
              contentContainerStyle={styles.modalScrollContent}
              keyboardShouldPersistTaps="handled"
              showsVerticalScrollIndicator={false}
            >
              {/* Avatar Picker Section */}
              <View style={styles.avatarEditSection}>
                <TouchableOpacity
                  style={styles.avatarEditTouchable}
                  onPress={handlePickImage}
                  disabled={isUploadingPhoto}
                  activeOpacity={0.85}
                >
                  {editAvatarUri ? (
                    <Image source={{ uri: editAvatarUri }} style={styles.avatarEditImage} />
                  ) : (
                    <View style={styles.avatarEditFallback}>
                      <Text style={styles.avatarEditInitial}>
                        {editName ? editName.charAt(0).toUpperCase() : 'U'}
                      </Text>
                    </View>
                  )}

                  {isUploadingPhoto ? (
                    <View style={styles.avatarUploadingOverlay}>
                      <ActivityIndicator size="small" color="#FFFFFF" />
                    </View>
                  ) : (
                    <View style={styles.cameraBadge}>
                      <CameraIcon size={16} color="#FFFFFF" />
                    </View>
                  )}
                </TouchableOpacity>

                <TouchableOpacity
                  onPress={handlePickImage}
                  disabled={isUploadingPhoto}
                  style={styles.changePhotoTextButton}
                >
                  <Text style={styles.changePhotoText}>
                    {isUploadingPhoto ? 'Uploading photo...' : 'Change Profile Picture'}
                  </Text>
                </TouchableOpacity>
              </View>

              {/* Form Fields */}
              <View style={styles.formContainer}>
                {/* Username Field */}
                <View style={styles.inputGroup}>
                  <View style={styles.inputLabelRow}>
                    <Text style={styles.inputLabel}>USERNAME</Text>
                  </View>

                  <View
                    style={[
                      styles.usernameInputContainer,
                      usernameError ? styles.inputContainerError : null,
                    ]}
                  >
                    <Text style={styles.usernamePrefix}>@</Text>
                    <TextInput
                      style={styles.usernameTextInput}
                      value={editUsername}
                      onChangeText={(text) => {
                        const sanitized = text.toLowerCase().replace(/[^a-z0-9_]/g, '');
                        setEditUsername(sanitized);
                        if (usernameError) setUsernameError(null);
                      }}
                      placeholder="username"
                      placeholderTextColor="#555555"
                      autoCapitalize="none"
                      autoCorrect={false}
                      maxLength={30}
                    />
                    {editUsername.length >= 3 && !usernameError && (
                      <View style={styles.inputCheckmark}>
                        <CheckIcon size={16} color="#10B981" />
                      </View>
                    )}
                  </View>

                  {usernameError ? (
                    <View style={styles.errorBanner}>
                      <Text style={styles.errorText}>{usernameError}</Text>
                    </View>
                  ) : (
                    <Text style={styles.fieldHint}>
                      3–30 characters. Letters, numbers, and underscores only.
                    </Text>
                  )}
                </View>

                {/* Display Name Field */}
                <View style={styles.inputGroup}>
                  <Text style={styles.inputLabel}>DISPLAY NAME</Text>
                  <TextInput
                    style={styles.textInput}
                    value={editName}
                    onChangeText={setEditName}
                    placeholder="Enter your name"
                    placeholderTextColor="#555555"
                    maxLength={50}
                  />
                  <Text style={styles.fieldHint}>
                    This name will appear on your profile.
                  </Text>
                </View>
              </View>

              {/* Save Button */}
              <TouchableOpacity
                style={[styles.saveChangesButton, isSaving && styles.saveChangesButtonDisabled]}
                onPress={handleSaveProfile}
                disabled={isSaving || isUploadingPhoto}
                activeOpacity={0.85}
              >
                {isSaving ? (
                  <ActivityIndicator size="small" color="#FFFFFF" />
                ) : (
                  <Text style={styles.saveChangesText}>Save Changes</Text>
                )}
              </TouchableOpacity>
            </ScrollView>
          </KeyboardAvoidingView>
        </SafeAreaView>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#000000',
  },
  header: {
    paddingHorizontal: 20,
    paddingTop: 4,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#1A1A1A',
  },
  headerTitle: {
    color: '#FFFFFF',
    fontFamily: 'ChangaOne-Regular',
    fontSize: 20,
    letterSpacing: 0.3,
  },
  scrollContent: {
    paddingHorizontal: 20,
    paddingTop: 20,
    paddingBottom: 40,
    gap: 20,
  },
  userCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#111113',
    borderColor: '#222225',
    borderWidth: 1,
    borderRadius: 16,
    padding: 18,
    gap: 16,
  },
  avatarContainer: {
    position: 'relative',
  },
  avatar: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: '#1C1C1E',
  },
  avatarFallback: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: '#1E1B2E',
    borderColor: '#3B2D54',
    borderWidth: 1.5,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarInitial: {
    color: '#EC4899',
    fontFamily: 'ChangaOne-Regular',
    fontSize: 28,
  },
  userTextInfo: {
    flex: 1,
    gap: 4,
  },
  userName: {
    color: '#FFFFFF',
    fontFamily: 'ChangaOne-Regular',
    fontSize: 18,
    letterSpacing: 0.2,
  },
  handleBadge: {
    alignSelf: 'flex-start',
    backgroundColor: '#1A1224',
    borderColor: '#3B2D54',
    borderWidth: 1,
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 2,
    marginTop: 2,
  },
  handleText: {
    color: '#EC4899',
    fontSize: 13,
    fontWeight: '600',
    letterSpacing: 0.2,
  },
  userEmail: {
    color: '#8E8E93',
    fontSize: 13,
    marginTop: 2,
  },
  editProfileButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#141418',
    borderColor: '#27272A',
    borderWidth: 1,
    borderRadius: 14,
    paddingHorizontal: 16,
    paddingVertical: 14,
  },
  editButtonContent: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
  },
  editIconCircle: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: '#271B38',
    borderColor: '#4A2E6E',
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  editButtonTextContainer: {
    gap: 2,
  },
  editButtonTitle: {
    color: '#FFFFFF',
    fontFamily: 'ChangaOne-Regular',
    fontSize: 15,
  },
  editButtonSubtitle: {
    color: '#8E8E93',
    fontSize: 12,
  },
  editButtonArrow: {
    color: '#71717A',
    fontSize: 22,
    fontWeight: '300',
  },
  signOutButton: {
    backgroundColor: '#181212',
    borderColor: '#3D1D1D',
    borderWidth: 1,
    borderRadius: 14,
    paddingVertical: 15,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 10,
  },
  signOutText: {
    color: '#EF4444',
    fontFamily: 'ChangaOne-Regular',
    fontSize: 16,
  },

  /* Unauthenticated / Guest View Styles */
  guestContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 28,
    paddingBottom: 60,
  },
  guestIconCircle: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: '#1C1524',
    borderWidth: 1.5,
    borderColor: '#3D2254',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 20,
  },
  guestTitle: {
    color: '#FFFFFF',
    fontFamily: 'ChangaOne-Regular',
    fontSize: 22,
    letterSpacing: 0.3,
    marginBottom: 8,
    textAlign: 'center',
  },
  guestSubtitle: {
    color: '#8E8E93',
    fontSize: 14,
    lineHeight: 21,
    textAlign: 'center',
    marginBottom: 28,
  },
  guestButton: {
    backgroundColor: '#E11D48',
    borderRadius: 14,
    paddingVertical: 15,
    paddingHorizontal: 28,
    alignItems: 'center',
    justifyContent: 'center',
    width: '100%',
    maxWidth: 320,
  },
  guestButtonText: {
    color: '#FFFFFF',
    fontFamily: 'ChangaOne-Regular',
    fontSize: 16,
    letterSpacing: 0.3,
  },

  /* Edit Profile Modal Styles */
  modalContainer: {
    flex: 1,
    backgroundColor: '#0A0A0C',
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#1A1A1E',
  },
  modalCloseButton: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#16161A',
    alignItems: 'center',
    justifyContent: 'center',
  },
  modalTitle: {
    color: '#FFFFFF',
    fontFamily: 'ChangaOne-Regular',
    fontSize: 18,
  },
  modalSaveButton: {
    backgroundColor: '#E11D48',
    paddingHorizontal: 16,
    paddingVertical: 7,
    borderRadius: 18,
    minWidth: 62,
    alignItems: 'center',
    justifyContent: 'center',
  },
  modalSaveButtonDisabled: {
    opacity: 0.6,
  },
  modalSaveText: {
    color: '#FFFFFF',
    fontFamily: 'ChangaOne-Regular',
    fontSize: 14,
  },
  modalKeyboardAvoid: {
    flex: 1,
  },
  modalScrollContent: {
    paddingHorizontal: 20,
    paddingTop: 24,
    paddingBottom: 40,
    gap: 24,
  },
  avatarEditSection: {
    alignItems: 'center',
    gap: 12,
  },
  avatarEditTouchable: {
    position: 'relative',
  },
  avatarEditImage: {
    width: 104,
    height: 104,
    borderRadius: 52,
    borderWidth: 2,
    borderColor: '#EC4899',
    backgroundColor: '#16161A',
  },
  avatarEditFallback: {
    width: 104,
    height: 104,
    borderRadius: 52,
    backgroundColor: '#1E1B2E',
    borderWidth: 2,
    borderColor: '#EC4899',
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarEditInitial: {
    color: '#EC4899',
    fontFamily: 'ChangaOne-Regular',
    fontSize: 44,
  },
  cameraBadge: {
    position: 'absolute',
    bottom: 2,
    right: 2,
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: '#E11D48',
    borderColor: '#0A0A0C',
    borderWidth: 2.5,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarUploadingOverlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    borderRadius: 52,
    backgroundColor: 'rgba(0,0,0,0.65)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  changePhotoTextButton: {
    paddingVertical: 4,
    paddingHorizontal: 12,
  },
  changePhotoText: {
    color: '#EC4899',
    fontSize: 14,
    fontWeight: '600',
  },
  formContainer: {
    gap: 20,
  },
  inputGroup: {
    gap: 8,
  },
  inputLabelRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  inputLabel: {
    color: '#A1A1AA',
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 0.6,
  },
  usernameInputContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#141416',
    borderColor: '#2A2A2E',
    borderWidth: 1,
    borderRadius: 12,
    paddingHorizontal: 14,
  },
  inputContainerError: {
    borderColor: '#EF4444',
  },
  usernamePrefix: {
    color: '#EC4899',
    fontSize: 16,
    fontWeight: '700',
    marginRight: 4,
  },
  usernameTextInput: {
    flex: 1,
    color: '#FFFFFF',
    fontSize: 15,
    paddingVertical: 13,
  },
  inputCheckmark: {
    paddingLeft: 8,
  },
  textInput: {
    backgroundColor: '#141416',
    borderColor: '#2A2A2E',
    borderWidth: 1,
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 13,
    color: '#FFFFFF',
    fontSize: 15,
  },
  fieldHint: {
    color: '#71717A',
    fontSize: 12,
  },
  errorBanner: {
    backgroundColor: '#271113',
    borderColor: '#541D22',
    borderWidth: 1,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    marginTop: 2,
  },
  errorText: {
    color: '#F87171',
    fontSize: 13,
    fontWeight: '500',
  },
  saveChangesButton: {
    backgroundColor: '#E11D48',
    borderRadius: 14,
    paddingVertical: 15,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 8,
  },
  saveChangesButtonDisabled: {
    opacity: 0.6,
  },
  saveChangesText: {
    color: '#FFFFFF',
    fontFamily: 'ChangaOne-Regular',
    fontSize: 16,
    letterSpacing: 0.3,
  },
});
