import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Lock } from 'lucide-react'
import { loginSchema, type LoginFormData } from '../schemas'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Alert } from '@/components/ui/Alert'
import type { ApiError } from '@/types'

interface LoginFormProps {
  onSubmit:     (data: LoginFormData) => void
  isLoading:    boolean
  error?:       ApiError | null
  prefillEmail?: string
}

export function LoginForm({ onSubmit, isLoading, error, prefillEmail }: LoginFormProps) {
  const { register, handleSubmit, formState: { errors } } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: prefillEmail ?? '' },
  })

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      {error && (
        <Alert variant="error" message={error.message ?? 'Login failed. Please try again.'} />
      )}

      <Input
        {...register('email')}
        type="email"
        label="Email address"
        placeholder="you@healthcare.org"
        autoComplete="email"
        error={errors.email?.message}
      />

      <Input
        {...register('password')}
        type="password"
        label="Password"
        placeholder="••••••••"
        autoComplete="current-password"
        error={errors.password?.message}
      />

      <Button type="submit" loading={isLoading} leftIcon={<Lock className="w-4 h-4" />} className="w-full">
        Sign in securely
      </Button>
    </form>
  )
}