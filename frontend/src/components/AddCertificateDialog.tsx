import { Plus } from 'lucide-react';
import { useState, type FormEvent } from 'react';

import { apiErrorMessage, apiFieldErrors } from '@/api/client';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useCreateCertificate } from '@/hooks/useCertificates';
import { useToast } from '@/hooks/use-toast';

const EMPTY = {
  cert_number: '',
  student_name: '',
  roll_number: '',
  programme: '',
  year_of_passing: '',
  cgpa: '',
  marks: '',
  issue_date: '',
};

type FormState = typeof EMPTY;

const FIELDS: { name: keyof FormState; label: string; type?: string; hint?: string }[] = [
  { name: 'cert_number', label: 'Certificate number', hint: 'Stored without spaces/punctuation' },
  { name: 'student_name', label: 'Student name' },
  { name: 'roll_number', label: 'Roll number' },
  { name: 'programme', label: 'Programme' },
  { name: 'year_of_passing', label: 'Year of passing', type: 'number' },
  { name: 'issue_date', label: 'Issue date', type: 'date' },
  { name: 'cgpa', label: 'CGPA (0–10)', type: 'number', hint: 'CGPA or marks, at least one' },
  { name: 'marks', label: 'Marks (%)', type: 'number' },
];

export default function AddCertificateDialog() {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<FormState>(EMPTY);
  const create = useCreateCertificate();
  const { toast } = useToast();

  const fieldErrors = create.isError ? apiFieldErrors(create.error) : {};
  const formError =
    create.isError && Object.keys(fieldErrors).every((k) => k === '_form')
      ? (fieldErrors._form ?? apiErrorMessage(create.error))
      : fieldErrors._form;

  function onOpenChange(next: boolean) {
    setOpen(next);
    if (!next) {
      setForm(EMPTY);
      create.reset();
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    create.mutate(
      {
        cert_number: form.cert_number,
        student_name: form.student_name,
        roll_number: form.roll_number,
        programme: form.programme,
        year_of_passing: Number(form.year_of_passing),
        cgpa: form.cgpa || null,
        marks: form.marks || null,
        issue_date: form.issue_date,
      },
      {
        onSuccess: (cert) => {
          toast({ title: 'Certificate added', description: `${cert.cert_number} is signed and stored.` });
          onOpenChange(false);
        },
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger asChild>
        <Button>
          <Plus />
          Add certificate
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-xl">
        <form onSubmit={onSubmit} className="space-y-6">
          <DialogHeader>
            <DialogTitle>Add certificate</DialogTitle>
            <DialogDescription>
              The record is normalized and signed with your institution&apos;s key.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 sm:grid-cols-2">
            {FIELDS.map((f) => (
              <div key={f.name} className="space-y-1.5">
                <Label htmlFor={f.name}>{f.label}</Label>
                <Input
                  id={f.name}
                  type={f.type ?? 'text'}
                  step={f.type === 'number' && f.name !== 'year_of_passing' ? '0.01' : undefined}
                  required={f.name !== 'cgpa' && f.name !== 'marks'}
                  value={form[f.name]}
                  aria-invalid={Boolean(fieldErrors[f.name])}
                  onChange={(e) => setForm({ ...form, [f.name]: e.target.value })}
                />
                {fieldErrors[f.name] ? (
                  <p className="text-xs text-destructive">{fieldErrors[f.name]}</p>
                ) : (
                  f.hint && <p className="text-xs text-muted-foreground">{f.hint}</p>
                )}
              </div>
            ))}
          </div>

          {formError && (
            <p role="alert" className="text-sm text-destructive">
              {formError}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? 'Saving…' : 'Save certificate'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
