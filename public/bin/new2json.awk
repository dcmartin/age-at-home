BEGIN {
    FS=","
    OFS=""
    getline
    for ( i=1; i<=NF; i++) names[i] = ($i)
    printf "{ 'seqid': '%s', 'rows':[\n", seqid
    j = 1
}
{
    if (j > 1) printf ",\n"
    printf "{"
    for (i = 1; i<=NF; i++)
    {
	printf "'%s':'%s'%s", names[i], $i, (i == NF ? "" : ",")
    }
    printf "}"
    j = j + 1
}
END {
    printf " ] }\n"
}
