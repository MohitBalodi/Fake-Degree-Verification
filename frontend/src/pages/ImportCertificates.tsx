import axios from 'axios';
import { Download, FileUp } from 'lucide-react';
import { useRef, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';

import { apiErrorMessage } from '@/api/client';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useMe } from '@/hooks/useAuth';
import { useImportCertificates, type ImportErrorResponse } from '@/hooks/useCertificates';
import { useToast } from '@/hooks/use-toast';

const COLUMNS = [
  'cert_number',
  'institution_code',
  'student_name',
  'roll_number',
  'programme',
  'year_of_passing',
  'cgpa',
  'marks',
  'issue_date',
];

function downloadTemplate(institutionCode: string) {
  const example = [
    `${institutionCode}2024XX0001`,
    institutionCode,
    'Sample Student',
    '20XX001',
    'B.Tech Example Programme',
    '2024',
    '8.25',
    '',
    '2024-07-20',
  ];
  const csv = `${COLUMNS.join(',')}\n${example.join(',')}\n`;
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = 'certificates-template.csv';
  a.click();
  URL.revokeObjectURL(url);
}

export default function ImportCertificates() {
  const { data: user } = useMe();
  const upload = useImportCertificates();
  const { toast } = useToast();
  const [file, setFile] = useState<File | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const code = user?.institution?.code ?? 'CODE';
  const errorBody =
    upload.isError && axios.isAxiosError(upload.error)
      ? (upload.error.response?.data as ImportErrorResponse | undefined)?.error
      : undefined;
  const rowErrors = errorBody?.rows ?? [];

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    upload.mutate(file, {
      onSuccess: (result) => {
        toast({
          title: 'Import complete',
          description: `${result.imported} certificate${result.imported === 1 ? '' : 's'} signed and added.`,
        });
        setFile(null);
        if (inputRef.current) inputRef.current.value = '';
      },
    });
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Import certificates</h1>
        <p className="text-sm text-muted-foreground">
          Upload a CSV. Every row is checked first — if any row has a problem, nothing is
          imported.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">CSV file</CardTitle>
          <CardDescription>
            UTF-8, header row required, columns in any order. Dates as YYYY-MM-DD. Give CGPA,
            marks (%), or both. <span className="font-mono">institution_code</span> must be{' '}
            <span className="font-mono">{code}</span>.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="break-all rounded-md bg-muted px-3 py-2 font-mono text-xs">
            {COLUMNS.join(',')}
          </p>
          <form onSubmit={onSubmit} className="flex flex-wrap items-end gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="csv">File</Label>
              <Input
                id="csv"
                ref={inputRef}
                type="file"
                accept=".csv,text/csv"
                className="max-w-xs"
                onChange={(e) => {
                  setFile(e.target.files?.[0] ?? null);
                  upload.reset();
                }}
              />
            </div>
            <Button type="submit" disabled={!file || upload.isPending}>
              <FileUp />
              {upload.isPending ? 'Checking…' : 'Upload and import'}
            </Button>
            <Button type="button" variant="ghost" onClick={() => downloadTemplate(code)}>
              <Download />
              Template
            </Button>
          </form>
        </CardContent>
      </Card>

      {upload.isSuccess && (
        <Card>
          <CardContent className="flex flex-wrap items-center justify-between gap-3 pt-6">
            <p className="text-sm">
              Imported <span className="font-semibold">{upload.data.imported}</span>{' '}
              certificate{upload.data.imported === 1 ? '' : 's'}.
            </p>
            <Button variant="outline" size="sm" asChild>
              <Link to="/certificates">View certificates</Link>
            </Button>
          </CardContent>
        </Card>
      )}

      {upload.isError && (
        <Card className="border-destructive/50">
          <CardHeader>
            <CardTitle className="text-base text-destructive">Nothing was imported</CardTitle>
            <CardDescription>{errorBody?.message ?? apiErrorMessage(upload.error)}</CardDescription>
          </CardHeader>
          {rowErrors.length > 0 && (
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-20">Line</TableHead>
                    <TableHead className="w-40">Column</TableHead>
                    <TableHead>Problem</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rowErrors.map((e, i) => (
                    <TableRow key={`${e.row}-${e.field}-${i}`}>
                      <TableCell className="tabular-nums">{e.row}</TableCell>
                      <TableCell className="font-mono text-xs">{e.field ?? '(row)'}</TableCell>
                      <TableCell>{e.message}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          )}
        </Card>
      )}
    </div>
  );
}
