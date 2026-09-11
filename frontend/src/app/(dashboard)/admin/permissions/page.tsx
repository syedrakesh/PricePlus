'use client';

import React, { useState } from 'react';
import useSWR from 'swr';
import { adminApi, PermissionItem, RoleItem } from '@/lib/api';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Badge } from '@/components/ui/Badge';
import { PageLoader } from '@/components/ui/Spinner';
import styles from './page.module.css';

export default function AdminPermissionsPage() {
  const { data: permissions = [], mutate: mutatePerms, isLoading: loadingPerms } = useSWR(
    'admin-permissions',
    adminApi.listPermissions
  );
  const { data: roles = [], mutate: mutateRoles, isLoading: loadingRoles } = useSWR(
    'admin-roles',
    adminApi.listRoles
  );

  const [savingRoleId, setSavingRoleId] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [newSlug, setNewSlug] = useState<string>('');
  const [newName, setNewName] = useState<string>('');
  const [newDesc, setNewDesc] = useState<string>('');
  const [createLoading, setCreateLoading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string>('');

  // Group permissions by category
  const categories = Array.from(new Set(permissions.map(p => p.category)));

  async function handleTogglePermission(role: RoleItem, permCode: string) {
    const isAssigned = role.permissions.includes(permCode);
    const updatedPermissions = isAssigned
      ? role.permissions.filter(c => c !== permCode)
      : [...role.permissions, permCode];

    setSavingRoleId(role.id);
    try {
      await adminApi.updateRoleMatrix(role.id, updatedPermissions);
      await mutateRoles();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Failed to update matrix');
    } finally {
      setSavingRoleId(null);
    }
  }

  async function handleCreateRole(e: React.FormEvent) {
    e.preventDefault();
    if (!newSlug || !newName) return;

    setCreateLoading(true);
    setErrorMsg('');
    try {
      await adminApi.createRole({
        slug: newSlug.toLowerCase().trim().replace(/\s+/g, '_'),
        name: newName.trim(),
        description: newDesc.trim(),
        permissions: [],
      });
      await mutateRoles();
      setShowCreateModal(false);
      setNewSlug('');
      setNewName('');
      setNewDesc('');
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to create role');
    } finally {
      setCreateLoading(false);
    }
  }

  async function handleDeleteRole(roleId: string, roleName: string) {
    if (!confirm(`Are you sure you want to delete custom role "${roleName}"?`)) return;
    try {
      await adminApi.deleteRole(roleId);
      await mutateRoles();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Failed to delete role');
    }
  }

  if (loadingPerms || loadingRoles) {
    return <PageLoader />;
  }

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <div>
          <h1 className={styles.title}>Dynamic Role & Permission Matrix</h1>
          <p className={styles.subtitle}>
            Manage system roles, create custom user groups, and toggle permission matrix access live.
          </p>
        </div>
        <Button onClick={() => setShowCreateModal(true)}>+ Create Custom Role</Button>
      </header>

      <Card className={styles.matrixCard}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th style={{ width: '320px' }}>Permission / Feature</th>
              {roles.map(r => (
                <th key={r.id} className={styles.roleHeaderCell}>
                  <div className={styles.roleTitle}>
                    <span>{r.name}</span>
                    {r.is_system ? (
                      <Badge variant="info" style={{ fontSize: '9px', padding: '1px 4px' }}>
                        System
                      </Badge>
                    ) : (
                      <button
                        onClick={() => handleDeleteRole(r.id, r.name)}
                        style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#ef4444', fontSize: '11px' }}
                        title="Delete Role"
                      >
                        ✕
                      </button>
                    )}
                  </div>
                  <div className={styles.roleSlug}>{r.slug}</div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {categories.map(category => {
              const categoryPerms = permissions.filter(p => p.category === category);
              return (
                <React.Fragment key={category}>
                  <tr className={styles.categoryRow}>
                    <td colSpan={roles.length + 1} className={styles.categoryTitle}>
                      📂 {category}
                    </td>
                  </tr>
                  {categoryPerms.map(perm => (
                    <tr key={perm.code}>
                      <td>
                        <div className={styles.permName}>{perm.name}</div>
                        <span className={styles.permCode}>{perm.code}</span>
                        <div className={styles.permDesc}>{perm.description}</div>
                      </td>
                      {roles.map(role => {
                        const checked = role.permissions.includes(perm.code);
                        const disabled = savingRoleId === role.id;

                        return (
                          <td key={role.id} className={styles.cellCenter}>
                            <input
                              type="checkbox"
                              className={styles.checkbox}
                              checked={checked}
                              disabled={disabled}
                              onChange={() => handleTogglePermission(role, perm.code)}
                            />
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </Card>

      {showCreateModal && (
        <div className={styles.modalOverlay} onClick={() => setShowCreateModal(false)}>
          <div className={styles.modal} onClick={e => e.stopPropagation()}>
            <h3 className={styles.modalTitle}>Create Custom Role</h3>
            <form onSubmit={handleCreateRole} className={styles.form}>
              <Input
                label="Role Name"
                value={newName}
                onChange={e => {
                  setNewName(e.target.value);
                  if (!newSlug) setNewSlug(e.target.value.toLowerCase().replace(/\s+/g, '_'));
                }}
                placeholder="e.g. Store Auditor"
                required
              />
              <Input
                label="Role Slug"
                value={newSlug}
                onChange={e => setNewSlug(e.target.value)}
                placeholder="e.g. store_auditor"
                required
              />
              <Input
                label="Description"
                value={newDesc}
                onChange={e => setNewDesc(e.target.value)}
                placeholder="Brief summary of role responsibilities"
              />

              {errorMsg && <p style={{ color: 'var(--color-danger)', fontSize: '13px' }}>{errorMsg}</p>}

              <div className={styles.actions}>
                <Button type="button" variant="secondary" onClick={() => setShowCreateModal(false)}>
                  Cancel
                </Button>
                <Button type="submit" loading={createLoading}>
                  Save Role
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
